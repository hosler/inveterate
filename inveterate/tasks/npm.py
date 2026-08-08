import requests.exceptions
from celery import shared_task
from celery_singleton import Singleton

from ..models import DomainRoute, PortForward, PortGateway, ServiceNetwork
from ._common import logger


class NPMTransientError(Exception):
    """Wraps a 5xx response from NPM itself.

    Kept distinct from a generic ``requests.exceptions.HTTPError`` so that
    ``autoretry_for`` can target "this is probably transient, try again"
    failures (connection errors, timeouts, NPM 5xx) without also retrying a
    genuine permanent rejection (e.g. a 4xx).
    """


# Exception types worth an automatic retry: the network/NPM hiccupped, not a
# permanent rejection. A 404 on delete is handled separately as success (the
# resource is already gone), never raised.
_NPM_RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    NPMTransientError,
)


def _get_npm_client(gateway):
    from ..npm import NPMClient

    return NPMClient(gateway.host, gateway.admin_email, gateway.admin_password)


def _raise_unless_already_gone(e, resource_desc):
    """Classify an ``HTTPError`` from an NPM delete call.

    * 404            -> resource is already gone; treated as success (returns).
    * 5xx            -> likely transient; re-raised as ``NPMTransientError`` so
                        ``autoretry_for`` retries it.
    * anything else  -> permanent failure; re-raised as-is (no retry).
    """
    status = e.response.status_code if e.response is not None else None
    if status == 404:
        logger.info("%s already deleted (404)", resource_desc)
        return
    if status is not None and status >= 500:
        logger.error("NPM returned a server error deleting %s: %s", resource_desc, e)
        raise NPMTransientError(str(e)) from e
    logger.error("HTTP error deleting %s: %s", resource_desc, e)
    raise


@shared_task(name="inveterate.tasks.sync_port_forward", base=Singleton, lock_expiry=60 * 15)
def sync_port_forward(port_forward_id):
    """Create or update the NPM stream for a PortForward record."""
    logger.info("Syncing port forward %s to NPM", port_forward_id)
    pf = PortForward.objects.select_related("port_block__gateway", "port_block__service_network__ip").get(
        pk=port_forward_id
    )

    client = _get_npm_client(pf.port_block.gateway)
    forwarding_host = pf.port_block.service_network.ip.value
    tcp = pf.protocol in ("tcp", "both")
    udp = pf.protocol in ("udp", "both")

    try:
        if pf.npm_stream_id:
            client.update_stream(
                pf.npm_stream_id,
                incoming_port=pf.external_port,
                forwarding_host=forwarding_host,
                forwarding_port=pf.internal_port,
                tcp_forwarding=tcp,
                udp_forwarding=udp,
            )
            logger.info("Updated NPM stream %s for port forward %s", pf.npm_stream_id, pf.id)
        else:
            result = client.create_stream(
                incoming_port=pf.external_port,
                forwarding_host=forwarding_host,
                forwarding_port=pf.internal_port,
                tcp=tcp,
                udp=udp,
            )
            pf.npm_stream_id = result["id"]
            pf.save(update_fields=["npm_stream_id"])
            logger.info("Created NPM stream %s for port forward %s", pf.npm_stream_id, pf.id)
    except Exception as e:
        logger.error("Failed to sync port forward %s to NPM: %s", pf.id, e)
        raise


@shared_task(name="inveterate.tasks.sync_domain_route", base=Singleton, lock_expiry=60 * 15)
def sync_domain_route(domain_route_id):
    """Create or update the NPM proxy host for a DomainRoute record."""
    logger.info("Syncing domain route %s to NPM", domain_route_id)
    dr = DomainRoute.objects.select_related("service").get(pk=domain_route_id)

    # Find the internal IP and gateway for this service
    internal_sn = (
        ServiceNetwork.objects.filter(service=dr.service, ip__pool__internal=True)
        .select_related("ip", "port_block__gateway")
        .first()
    )

    if not internal_sn or not hasattr(internal_sn, "port_block"):
        logger.error("No internal IP with port block for domain route %s", dr.id)
        return

    client = _get_npm_client(internal_sn.port_block.gateway)
    forward_host = internal_sn.ip.value

    try:
        if dr.npm_proxy_host_id:
            client.update_proxy_host(
                dr.npm_proxy_host_id,
                domain_names=[dr.domain],
                forward_host=forward_host,
                forward_port=dr.forward_port,
                ssl_forced=dr.force_ssl,
            )
            logger.info("Updated NPM proxy host %s for domain route %s", dr.npm_proxy_host_id, dr.id)
        else:
            result = client.create_proxy_host(
                domain=dr.domain,
                forward_host=forward_host,
                forward_port=dr.forward_port,
                ssl=dr.ssl,
                force_ssl=dr.force_ssl,
            )
            dr.npm_proxy_host_id = result["id"]
            dr.save(update_fields=["npm_proxy_host_id"])
            logger.info("Created NPM proxy host %s for domain route %s", dr.npm_proxy_host_id, dr.id)
    except Exception as e:
        logger.error("Failed to sync domain route %s to NPM: %s", dr.id, e)
        raise


@shared_task(
    name="inveterate.tasks.delete_npm_stream",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=_NPM_RETRYABLE_EXCEPTIONS,
    retry_backoff=5,
    retry_backoff_max=300,
    max_retries=5,
)
def delete_npm_stream(gateway_id, npm_stream_id):
    """Cleanup of an NPM stream.

    Transient failures (connection errors, timeouts, NPM 5xx) are retried
    automatically via ``autoretry_for``. A 404 means the stream is already
    gone and is treated as success. Any other failure propagates so this
    task is marked failed instead of silently "succeeding" -- callers (e.g.
    ``cancel_service``) rely on that to know when it's actually safe to
    release the IP the stream was pointing at.
    """
    logger.info("Deleting NPM stream %s on gateway %s", npm_stream_id, gateway_id)
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
    except PortGateway.DoesNotExist:
        logger.warning("Gateway %s not found, cannot delete stream %s", gateway_id, npm_stream_id)
        return

    client = _get_npm_client(gw)
    try:
        client.delete_stream(npm_stream_id)
        logger.info("Deleted NPM stream %s", npm_stream_id)
    except requests.exceptions.HTTPError as e:
        _raise_unless_already_gone(e, f"NPM stream {npm_stream_id}")


@shared_task(
    name="inveterate.tasks.delete_npm_proxy_host",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=_NPM_RETRYABLE_EXCEPTIONS,
    retry_backoff=5,
    retry_backoff_max=300,
    max_retries=5,
)
def delete_npm_proxy_host(gateway_id, npm_proxy_host_id):
    """Cleanup of an NPM proxy host.

    Same success/retry/failure semantics as ``delete_npm_stream`` -- see its
    docstring.
    """
    logger.info("Deleting NPM proxy host %s on gateway %s", npm_proxy_host_id, gateway_id)
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
    except PortGateway.DoesNotExist:
        logger.warning("Gateway %s not found, cannot delete proxy host %s", gateway_id, npm_proxy_host_id)
        return

    client = _get_npm_client(gw)
    try:
        client.delete_proxy_host(npm_proxy_host_id)
        logger.info("Deleted NPM proxy host %s", npm_proxy_host_id)
    except requests.exceptions.HTTPError as e:
        _raise_unless_already_gone(e, f"NPM proxy host {npm_proxy_host_id}")

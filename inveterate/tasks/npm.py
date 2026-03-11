import requests.exceptions
from celery import shared_task
from celery_singleton import Singleton

from ..models import DomainRoute, PortForward, PortGateway, ServiceNetwork
from ._common import logger


def _get_npm_client(gateway):
    from ..npm import NPMClient

    return NPMClient(gateway.host, gateway.admin_email, gateway.admin_password)


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


@shared_task(name="inveterate.tasks.delete_npm_stream", base=Singleton, lock_expiry=60 * 15)
def delete_npm_stream(gateway_id, npm_stream_id):
    """Fire-and-forget cleanup of an NPM stream."""
    logger.info("Deleting NPM stream %s on gateway %s", npm_stream_id, gateway_id)
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
        client = _get_npm_client(gw)
        client.delete_stream(npm_stream_id)
        logger.info("Deleted NPM stream %s", npm_stream_id)
    except PortGateway.DoesNotExist:
        logger.warning("Gateway %s not found, cannot delete stream %s", gateway_id, npm_stream_id)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.info("NPM stream %s already deleted (404)", npm_stream_id)
        else:
            logger.error("HTTP error deleting NPM stream %s: %s", npm_stream_id, e)
            raise
    except Exception as e:
        logger.error("Failed to delete NPM stream %s: %s", npm_stream_id, e)


@shared_task(name="inveterate.tasks.delete_npm_proxy_host", base=Singleton, lock_expiry=60 * 15)
def delete_npm_proxy_host(gateway_id, npm_proxy_host_id):
    """Fire-and-forget cleanup of an NPM proxy host."""
    logger.info("Deleting NPM proxy host %s on gateway %s", npm_proxy_host_id, gateway_id)
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
        client = _get_npm_client(gw)
        client.delete_proxy_host(npm_proxy_host_id)
        logger.info("Deleted NPM proxy host %s", npm_proxy_host_id)
    except PortGateway.DoesNotExist:
        logger.warning("Gateway %s not found, cannot delete proxy host %s", gateway_id, npm_proxy_host_id)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.info("NPM proxy host %s already deleted (404)", npm_proxy_host_id)
        else:
            logger.error("HTTP error deleting NPM proxy host %s: %s", npm_proxy_host_id, e)
            raise
    except Exception as e:
        logger.error("Failed to delete NPM proxy host %s: %s", npm_proxy_host_id, e)

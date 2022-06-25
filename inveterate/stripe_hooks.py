from djstripe import webhooks
from djstripe.models import Session, Subscription
from .tasks import provision_service, cancel_service, suspend_service, set_service_renewal, record_payment
from .models import Service
from datetime import datetime, timezone


@webhooks.handler_all()
def my_handler(event, **kwargs):
    print("Triggered webhook " + event.type)
    print(event.data)


@webhooks.handler("checkout.session.completed")
def session_completed(event, **kwargs):
    data = event.data["object"]
    Session.sync_from_stripe_data(data=data)
    service = Service.objects.get(pk=data["client_reference_id"])
    service.billing_id = data["subscription"]
    service.save()
    provision_service.delay(service.id)


@webhooks.handler("invoice.payment_succeeded")
def payment_succeeded(event, **kwargs):
    data = event.data["object"]
    service = Service.objects.get(billing_id=data["subscription"])
    amt = float(data["amount_paid"] / 100)
    record_payment(service_id=service.id, amt=amt, currency=data["currency"], reference_id=data["charge"])


@webhooks.handler("customer.subscription.deleted")
def session_completed(event, **kwargs):
    data = event.data["object"]
    try:
        service = Service.objects.get(billing_id=data["id"])
        cancel_service.delay(service.id)
    except Service.DoesNotExist:
        pass


subscription_transitions = {
    'active': {
        'past_due': suspend_service
    }
}


@webhooks.handler("customer.subscription.updated")
def subscription_updated(event, **kwargs):
    data = event.data["object"]
    renewal_dtm = datetime.fromtimestamp(data["current_period_end"], timezone.utc)
    service = Service.objects.get(billing_id=data["id"])
    set_service_renewal(service.id, renewal_dtm)

    if "previous_attributes" in data:
        if "status" in data["previous_attributes"]:
            if data["previous_attributes"]["status"] in subscription_transitions:
                if data['status'] in subscription_transitions[data["previous_attributes"]["status"]]:
                    service = Service.objects.get(billing_id=data["id"])
                    subscription_transitions[data["previous_attributes"]["status"]][data['status']].delay(service.id)


@webhooks.handler("customer.subscription.deleted")
def subscription_deleted(event, **kwargs):
    data = event.data["object"]
    subscription = Subscription.objects.get(id=data["id"])
    service = Service.objects.get(id=subscription.metadata['inveterate_id'])
    epoch_end = data['canceled_at']
    cancel_date = datetime.fromtimestamp(epoch_end, timezone.utc)
    cancel_service(service.id, cancel_date=cancel_date)

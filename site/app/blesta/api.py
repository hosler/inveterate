from collections.abc import MutableMapping
import requests
from datetime import datetime
import urllib


class BlestaApi:
    def __init__(self, server, user, key):
        self.server = server
        self.user = user
        self.key = key

    def call(self, verb, classname, method, value_dict={}):
        api_target = 'https://' + self.server + '/api'
        urlstring = '/' + classname + '/' + method + '.json'
        print(urlstring)

        if verb.lower() == 'get':
            querystring = '?'
            for key, value in self.flatten(value_dict).items():
                querystring += key + '=' + str(value) + '&'
            r = requests.get(url=api_target + urlstring + querystring, auth=(self.user, self.key))

        elif verb.lower() == 'delete':
            querystring = '?'
            for key, value in self.flatten(value_dict).items():
                querystring += key + '=' + str(value) + '&'
            r = requests.delete(url=api_target + urlstring + querystring, auth=(self.user, self.key))

        elif verb.lower() == 'post':
            postdata = self.flatten(value_dict)
            r = requests.post(url=api_target + urlstring, auth=(self.user, self.key), data=postdata)

        elif verb.lower() == 'put':
            postdata = self.flatten(value_dict).items()
            r = requests.put(url=api_target + urlstring, auth=(self.user, self.key), data=postdata)

        else:
            raise Exception("Unrecognised HTTP verb: %s" % str(verb))

        if r.status_code != 200:
            raise Exception("Blesta API returned HTTP error response: %s" % str(r.status_code) + r.text)

        #print(r.text)
        response_dict = dict(r.json())
        response_dict['status'] = r.status_code
        if 'response' not in response_dict.keys():
            response_dict['response'] = ''

        return response_dict

    def blestadate_to_pythondate(self, blestadate):
        pythondate = datetime.strptime(str(blestadate), '%Y-%m-%d %H:%M:%S')
        return pythondate

    def blestacurrency_to_dollars(self, blestacurrency):
        dollars = '$' + blestacurrency[:-2]
        return dollars

    def flatten(self, d, parent_key=''):
        items = []
        for k, v in d.items():
            if isinstance(v, list):
                for i, j in enumerate(v):
                    new_key = f"{parent_key}[{k}][{str(i)}]" if parent_key else f"{k}[{str(i)}]"
                    items.extend(self.flatten(j, new_key).items())
            elif isinstance(v, dict):
                new_key = f"{parent_key}[{k}]" if parent_key else k
                items.extend(self.flatten(v, new_key).items())
            else:
                new_key = f"{parent_key}[{k}]" if parent_key else k
                if v is None:
                    items.append((new_key, ""))
                else:
                    items.append((new_key, v))
        return dict(items)

    def get_company_by_hostname(self, hostname):
        params = {'hostname': hostname}
        return self.call(verb='get', classname='companies', method='getByHostname', value_dict=params)["response"]

    def get_default_client_group(self, company_id):
        params = {
            'company_id': company_id
        }
        return self.call(verb='get', classname='client_groups', method='getDefault', value_dict=params)["response"]

    def create_user(self, username, password, client_group_id, first_name, last_name, email, username_type):
        params = {'vars': {
            'username': username,
            'new_password': password,
            'confirm_password': password,
            'client_group_id': client_group_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'settings': {
                'username_type': username_type,
                'tax_exempt': 'false',
                'tax_id': '',
                'default_currency': 'USD',
                'language': 'en_us',
            },
            'send_registration_email': 'false'}
        }
        return self.call(verb='post', classname='clients', method='create', value_dict=params)

    def create_package_group(self, company_id, name):
        params = {
            'vars': {
                'company_id': company_id,
                'names': {
                    '0': {
                        'name': name,
                        'lang': 'en_us'}
                },
            }
        }
        return self.call(verb='post', classname='package_groups', method='add', value_dict=params)["response"]

    def create_package(self, company_id, name, group_id, module_id, module_row_id):
        params = {
            'vars': {
                'company_id': company_id,
                'status': 'active',
                'module_id': module_id,
                'module_row': module_row_id,
                'names': {
                    '0': {
                        'name': name,
                        'lang': 'en_us'
                    }
                },
                'pricing': {
                    '0': {
                        'price': '0',
                        'currency': 'USD',
                        'term': 1,
                        'period': 'month'
                    }
                },
                'email_content': {
                    '0': {
                        'lang': 'en_us'
                    }
                },
                'groups': {
                    '0': group_id
                }
            }
        }
        return self.call(verb='post', classname='packages', method='add', value_dict=params)["response"]

    def edit_package(self, package_id, package_data):
        for k in list(package_data.keys()):
            if package_data[k] is None:
                package_data.pop(k)
            if k in ["groups"]:
                package_data.pop(k)
        params = {
            'package_id': package_id,
            'vars': package_data
        }
        return self.call(verb='post', classname='packages', method='edit', value_dict=params)["response"]

    def get_package_groups(self, company_id):
        params = {
            'company_id': company_id
        }
        return self.call(verb='get', classname='package_groups', method='getAll', value_dict=params)["response"]

    def get_package(self, company_id, name):
        params = {
            'company_id': company_id
        }
        packages = self.call(verb='get', classname='packages', method='getAll', value_dict=params)["response"]
        for package in packages:
            if package["name"] == name:
                return package

    def get_package_options(self, package_id):
        params = {
            'package_id': package_id
        }
        return self.call(verb='get', classname='package_options', method='getByPackageId', value_dict=params)[
            "response"]

    def get_service_options(self, service_id):
        params = {
            'service_id': service_id
        }
        return self.call(verb='get', classname='services', method='getOptions', value_dict=params)["response"]

    def get_package_details(self, package_id):
        params = {
            'package_id': package_id
        }

        return self.call(verb='get', classname='packages', method='get', value_dict=params)["response"]

    def get_all_modules(self, company_id):
        params = {
            'company_id': company_id
        }

        return self.call(verb='get', classname='module_manager', method='getAll', value_dict=params)["response"]

    def get_module_rows(self, module_id):
        params = {
            'module_id': module_id
        }

        return self.call(verb='get', classname='module_manager', method='getRows', value_dict=params)["response"]

    def get_module_groups(self, module_id):
        params = {
            'module_id': module_id
        }

        return self.call(verb='get', classname='module_manager', method='getGroups', value_dict=params)["response"]

    def search_user(self, username):
        params = {
            'username': username
        }

        return self.call(verb='get', classname='users', method='getByUsername', value_dict=params)["response"]

    def get_contacts(self, client_id):
        params = {
            "client_id": client_id
        }

        return self.call(verb='get', classname='contacts', method='getList', value_dict=params)["response"]

    def get_pricings(self, company_id):
        params = {
            "company_id": company_id
        }

        return self.call(verb='get', classname='pricings', method='getAll', value_dict=params)["response"]

    def add_price(self, company_id):
        params = {
            "vars": {
                "company_id": company_id
            }
        }

        return self.call(verb='post', classname='pricings', method='add', value_dict=params)["response"]

    def get_transaction_logs(self):
        params = {

        }

        return self.call(verb='get', classname='logs', method='getTransactionList', value_dict=params)["response"]

    def create_pay_links(self, contact, amount, currency):
        params = {
            "contact_info": contact,
            "amount": amount,
            "currency": currency,
        }
        return self.call(verb='get', classname='payments', method='getBuildProcess', value_dict=params)["response"]

    def create_pay_form(self, currency):
        params = {
            "currency": currency,
        }
        return self.call(verb='get', classname='payments', method='getBuildCcForm', value_dict=params)["response"]

    def get_service_invoices(self, service_id):
        params = {
            "service_id": service_id
        }
        return self.call(verb='get', classname='invoices', method='getAllWithService', value_dict=params)["response"]

    def get_plugins(self, company_id):
        params = {
            "company_id": company_id
        }
        return self.call(verb='get', classname='plugin_manager', method='getAll', value_dict=params)["response"]

    def get_events(self, plugin_id):
        params = {
            "plugin_id": plugin_id
        }
        return self.call(verb='get', classname='plugin_manager', method='getAllEvents', value_dict=params)["response"]

    def record_transaction(self, client_id, amount, currency, reference_id):
        params = {
            'vars': {
                "client_id": client_id,
                "amount": amount,
                "currency": currency,
                "reference_id": reference_id
            }
        }
        return self.call(verb='post', classname='transactions', method='add', value_dict=params)["response"]

    def apply_transaction(self, transaction_id, invoice_id, amount):
        params = {
            'transaction_id': transaction_id,
            'vars': {
                'amounts': {
                    '0': {
                        'invoice_id': invoice_id,
                        'amount': amount,
                    }
                }
            }
        }
        return self.call(verb='post', classname='transactions', method='apply', value_dict=params)["response"]

    def search_transactions(self, query):
        params = {
            'query': query,
        }
        return self.call(verb='get', classname='transactions', method='search', value_dict=params)["response"]

    def get_client_from_user(self, user_id):
        params = {
            'user_id': user_id
        }

        return self.call(verb='get', classname='clients', method='getByUserId', value_dict=params)["response"]

    def add_client_service(self, client_id, pricing_id, package_id):
        params = {
            'vars': {
                'client_id': client_id,
                'pricing_id': pricing_id,
                'status': 'pending',
                # 'configoptions': {
                #     'inveterate_id': inveterate_id
                # }
            },
            'packages': {"packages": package_id}
        }
        return self.call(verb='post', classname='services', method='add', value_dict=params)["response"]

    def get_service(self, service_id):
        params = {
            'service_id': service_id
        }
        return self.call(verb='get', classname='services', method='get', value_dict=params)["response"]

    def cancel_service(self, service_id, reason='', cancel_date=datetime.now(), use_module=False, reapply_payments=False, notify_cancel=False):
        if isinstance(cancel_date, datetime):
            cancel_date = datetime.strftime(cancel_date, '%Y-%m-%d %H:%M:%S')
        params = {
            'service_id': service_id,
            'vars': {
                'date_canceled': cancel_date,
                'use_module': use_module,
                'reapply_payments': reapply_payments,
                'notify_cancel': notify_cancel,
                'cancellation_reason': reason
            }
        }
        return self.call(verb='post', classname='services', method='cancel', value_dict=params)["response"]

    def get_client_services(self, client_id):
        params = {
            'client_id': client_id
        }
        return self.call(verb='get', classname='services', method='getList', value_dict=params)["response"]

    def edit_service(self, service_id, service_data):
        for k in list(service_data.keys()):
            if service_data[k] is None:
                service_data.pop(k)
        params = {
            'service_id': service_id,
            'vars': service_data
        }
        return self.call(verb='post', classname='services', method='edit', value_dict=params)["response"]

    def search_field(self, module_id, key, value):
        params = {
            'module_id': module_id,
            'key': key,
            'value': value
        }
        return self.call(verb='get', classname='services', method='searchServiceFields', value_dict=params)["response"]

    def set_inveterate_id(self, service_id, inveterate_id):
        params = {
            'service_id': service_id,
            'vars': {
                'vars': {
                    "key": "inveterate_id",
                    "value": inveterate_id
                }
            }
        }
        return self.call(verb='post', classname='services', method='setFields', value_dict=params)["response"]

    def create_service_invoice(self, client_id, service_id):
        params = {
            'client_id': client_id,
            'service_ids': {'service_ids': service_id},
            'currency': 'USD',
            'due_date': datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
        }
        return self.call(verb='post', classname='invoices', method='createFromServices', value_dict=params)[
            "response"]

    def get_service_invoices(self, service_id, status='open'):
        params = {
            'service_id': service_id,
            'status': status
        }
        return self.call(verb='post', classname='invoices', method='getAllWithService', value_dict=params)[
            "response"]

    def get_recurring_info(self, invoice_id):
        params = {
            'invoice_id': invoice_id,
        }
        return self.call(verb='post', classname='invoices', method='getRecurringInfo', value_dict=params)[
            "response"]

    def get_recurring(self, invoice_id):
        params = {
            'invoice_id': invoice_id,
        }
        return self.call(verb='post', classname='invoices', method='getRecurringFromInvoices', value_dict=params)[
            "response"]

    def create_pay_url(self, client_id, invoice_id):
        params = {
            'client_id': client_id,
            'invoice_id': invoice_id
        }

        hash = self.call(verb='post', classname='invoices', method='createPayHash', value_dict=params)["response"]

        params = {
            'text': f'c={client_id}|h={hash}',
        }

        url_hash = self.call(verb='post', classname='inveterate.InveterateModel', method='encrypt', value_dict=params)[
            "response"]

        hash_encoded = urllib.parse.quote_plus(url_hash)
        return f'http://{self.server}/client/pay/method/{invoice_id}/?sid={hash_encoded}'

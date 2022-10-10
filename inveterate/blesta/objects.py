import random
import string
import traceback


class BlestaObject:
    def __init__(self, api, hostname=None, company_id=None, *args, **kwargs):
        self.blesta = api
        self.__company_id = company_id
        self.hostname = hostname

    @property
    def company_id(self):
        if self.__company_id is None:
            if self.hostname is not None:
                self.__company_id = self.blesta.get_company_by_hostname(self.hostname)["id"]
        return self.__company_id


class BlestaUser(BlestaObject):
    def __init__(self, username=None, first_name=None, last_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__username = None
        self.__user = None
        self.client_id = None
        self.first_name = first_name
        self.last_name = last_name
        self.username = username

    @property
    def username(self):
        return self.__username

    @username.setter
    def username(self, value):
        self.__username = value
        self.__user = None
        try:
            self.user
        except Exception:
            traceback.print_exc()

    @property
    def user(self):
        if self.__user is None:
            try:
                blesta_user = self.blesta.search_user(self.username)
                if blesta_user is False:
                    client_group_id = self.blesta.get_default_client_group(self.company_id)["id"]
                    self.blesta.create_user(username=self.username, password=''.join(
                        random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in
                        range(10)), client_group_id=client_group_id, first_name=self.first_name,
                                            last_name=self.last_name,
                                            email=self.username, username_type="email")
                    blesta_user = self.blesta.search_user(self.username)
            except ConnectionError:
                traceback.print_exc()
            else:
                self.__user = blesta_user
                self.client_id = self.blesta.get_client_from_user(blesta_user["id"])["id"]
        return self.__user


class BlestaPlan(BlestaObject):
    def __init__(self, name, term, period, price, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__name = None
        self.__term = None
        self.__period = None
        self.__price = None
        self.__package_id = None
        self.__pricing_id = None
        self.__package = None

        self.name = name
        self.term = term
        self.period = period
        self.price = price
        self.module_id = None

    def set_price(self):
        self.__pricing_id = None
        if self.__term is not None and self.__period is not None and self.__price is not None:
            try:
                self.pricing_id
            except Exception:
                traceback.print_exc()

    @property
    def term(self):
        return self.__term

    @term.setter
    def term(self, value):
        self.__term = value
        self.set_price()

    @property
    def period(self):
        return self.__period

    @period.setter
    def period(self, value):
        self.__period = value
        self.set_price()

    @property
    def price(self):
        return self.__price

    @price.setter
    def price(self, value):
        self.__price = value
        self.set_price()

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value
        self.__package_id = None
        self.__pricing_id = None
        self.__package = None
        try:
            self.package
        except Exception:
            traceback.print_exc()

    @property
    def package_id(self):
        if self.__package_id is None:
            if self.__package is None:
                try:
                    self.__package_id = self.blesta.get_package(self.company_id, self.name)["id"]
                except TypeError:
                    self.__package_id = None
            else:
                self.__package_id = self.__package["id"]
        return self.__package_id

    @property
    def pricing_id(self):
        if self.__pricing_id is None:
            for price in self.package["pricing"]:
                if int(price["term"]) == self.term and price["period"] == self.period and float(
                        price["price"]) == self.price:
                    self.__pricing_id = price["id"]
                    break
            if self.__pricing_id is None:
                new_price = {
                    'term': self.term,
                    'period': self.period,
                    'price': self.price,
                    'price_renews': self.price,
                    'price_transfer': '0.0000',
                    'setup_fee': '0.0000',
                    'cancel_fee': '0.0000',
                    'currency': 'USD'
                }
                self.package["pricing"].append(new_price)
                self.blesta.edit_package(self.package_id, self.package)
                self.__package = self.blesta.get_package_details(self.package_id)
                for price in self.package["pricing"]:
                    if int(price["term"]) == self.term and price["period"] == self.period and float(
                            price["price"]) == self.price:
                        self.__pricing_id = price["id"]
                        break

        return self.__pricing_id

    @property
    def package(self):
        if self.__package is None:
            if self.package_id is None:
                groups = self.blesta.get_package_groups(company_id=self.company_id)
                group_id = None
                for group in groups:
                    if group["name"] == "inveterate":
                        group_id = group["id"]
                        break
                if group_id is None:
                    group_id = self.blesta.create_package_group(company_id=self.company_id, name="inveterate")
                modules = self.blesta.get_all_modules(self.company_id)
                module_id = None
                for module in modules:
                    if module["class"] == "universal_module":
                        module_id = module["id"]
                self.module_id = module_id
                module_rows = self.blesta.get_module_rows(self.module_id)
                module_row_id = None
                for module_row in module_rows:
                    if module_row['meta']['name'] == 'inveterate':
                        module_row_id = module_row['id']
                self.__package_id = self.blesta.create_package(company_id=self.company_id, name=self.name,
                                                               group_id=group_id,
                                                               module_id=module_id,
                                                               module_row_id=module_row_id)
            else:
                self.__package = self.blesta.get_package_details(self.__package_id)
        return self.__package


class BlestaService(BlestaObject):
    def __init__(self, plan=None, inveterate_id=None, service_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan
        self.__inveterate_id = None
        self.__service_id = None
        self.inveterate_id = inveterate_id
        self.service_id = service_id

        self.service = None

    @property
    def service_id(self):
        if self.__service_id:
            pass
        elif self.__inveterate_id:
            services = self.blesta.search_field(self.plan.module_id, 'inveterate_id', self.__inveterate_id)
            if len(services) > 0:
                self.service = services[0]

        return self.__service_id

    @property
    def inveterate_id(self):
        return self.__inveterate_id

    @inveterate_id.setter
    def inveterate_id(self, value):
        self.__inveterate_id = value
        try:
            self.blesta.set_inveterate_id(service_id=self.service_id, inveterate_id=self.__inveterate_id)
        except Exception:
            traceback.print_exc()

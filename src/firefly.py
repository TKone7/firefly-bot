import requests
import datetime

tx_attrs = ["type", "date", "amount", "description", "order", "currency_id", "currency_code", "foreign_amount",
            "foreign_currency_id", "foreign_currency_code", "USD", "budget_id", "category_id", "category_name",
            "source_id", "source_name", "destination_id", "destination_name", "reconciled", "piggy_bank_id",
            "piggy_bank_name", "bill_id", "bill_name", "tags", "notes", "internal_reference", "external_id",
            "bunq_payment_id", "sepa_cc", "sepa_ct_op", "sepa_ct_id", "sepa_db", "sepa_country", "sepa_ep", "sepa_ci",
            "sepa_batch_id", "interest_date", "book_date", "process_date", "due_date", "payment_date", "invoice_date"]

class Firefly(object):
    def __init__(self, hostname, auth_token):
        self.headers = {'Authorization': "Bearer " + auth_token}
        self.hostname = hostname + "/api/v1/"

    def _post(self, endpoint, payload):
        return requests.post("{}{}".format(self.hostname, endpoint), json=payload, headers=self.headers)

    def _put(self, endpoint, payload):
        return requests.put("{}{}".format(self.hostname, endpoint), json=payload, headers=self.headers)

    def _get(self, endpoint, params=None):
        response = requests.get("{}{}".format(
            self.hostname, endpoint), params=params, headers=self.headers)
        return response.json()

    def get_transactions(self, tx_type="all"):
        return self._get("transactions", params={"type": tx_type})

    def get_transaction(self, id):
        return self._get(f"transactions/{id}")

    def get_budgets(self):
        return self._get("budgets")

    def get_accounts(self, account_type="asset"):
        return self._get("accounts", params={"type": account_type})

    def get_rules(self):
        return self._get("rules")

    def get_account(self, id):
        return self._get(f"accounts/{id}")

    def get_bills(self):
        return self._get("bills")

    def get_about_user(self):
        return self._get("about/user")

    def update_transaction(self, id, **kwargs):
        payload = {
            "transactions": [{}]
        }
        for key, value in kwargs.items():
            if key not in tx_attrs:
                raise ValueError(f"Cannot set key {key} on a transaction")
            payload["transactions"][0][key] = value
        return self._put(endpoint=f"transactions/{id}", payload=payload)

    def create_transaction(self, **kwargs):
        if "type" not in kwargs.keys():
            raise ValueError(f"Must specify transaction type")
        now = datetime.datetime.now()
        payload = {
            "transactions": [{}]
        }
        for key, value in kwargs.items():
            if key not in tx_attrs:
                raise ValueError(f"Cannot set key {key} on a transaction")
            payload["transactions"][0][key] = value
        if not payload["transactions"][0]["date"]:
            payload["transactions"][0]["date"] = now.strftime("%Y-%m-%d")
        return self._post(endpoint="transactions", payload=payload)

    def create_withdrawal(self, amount, description, source_account, destination_account=None, category=None, budget=None):
        now = datetime.datetime.now()
        payload = {
            "transactions": [{
                "type": "withdrawal",
                "description": description,
                "date": now.strftime("%Y-%m-%d"),
                "amount": amount,
                "budget_name": budget,
                "category_name": category,
            }]
        }
        if source_account.isnumeric():
            payload["transactions"][0]["source_id"] = source_account
        else:
            payload["transactions"][0]["source_name"] = source_account

        if destination_account:
            if destination_account.isnumeric():
                payload["transactions"][0]["destination_id"] = destination_account
            else:
                payload["transactions"][0]["destination_name"] = destination_account
        else:
            payload["transactions"][0]["destination_name"] = description

        return self._post(endpoint="transactions", payload=payload)

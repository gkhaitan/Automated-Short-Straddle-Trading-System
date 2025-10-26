import webbrowser
from fyers_apiv3 import fyersModel
import trading_bot.config as config

class FyersAPI:
    def __init__(self):
        self.client_id = config.CLIENT_ID
        self.secret_key = config.SECRET_KEY
        self.redirect_uri = config.REDIRECT_URI
        self.fyers = None

    def _get_session_model(self):
        return fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )

    def generate_auth_code(self):
        """
        Generates an authentication code by opening a URL for the user to log in.
        The user needs to copy the auth_code from the redirected URL.
        """
        session = self._get_session_model()
        response = session.generate_authcode()
        print(f"Login URL: {response}")
        webbrowser.open(response, new=1)
        auth_code = input("Please enter the auth_code from the redirected URL: ")
        return auth_code

    def set_access_token(self, auth_code):
        """
        Sets the access token for the Fyers API session.
        """
        session = self._get_session_model()
        session.set_token(auth_code)
        response = session.generate_token()
        access_token = response["access_token"]

        self.fyers = fyersModel.FyersModel(
            client_id=self.client_id,
            is_async=False,
            token=access_token,
            log_path=""
        )
        print("Successfully generated access token!")

    def get_profile(self):
        """
        Fetches the user's profile details.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        return self.fyers.get_profile()

    def get_historical_data(self, symbol, resolution, date_format, range_from, range_to, cont_flag):
        """
        Fetches historical data for a given symbol.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": date_format,
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": cont_flag
        }
        return self.fyers.history(data)

    def get_quotes(self, symbols):
        """
        Fetches quotes for a given list of symbols.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        data = {"symbols": ",".join(symbols)}
        return self.fyers.quotes(data)

    def place_order(self, symbol, qty, type, side, productType, limitPrice=0, stopPrice=0, validity='DAY', disclosedQty=0, offlineOrder=False):
        """
        Places an order.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        data = {
            "symbol": symbol,
            "qty": qty,
            "type": type,
            "side": side,
            "productType": productType,
            "limitPrice": limitPrice,
            "stopPrice": stopPrice,
            "validity": validity,
            "disclosedQty": disclosedQty,
            "offlineOrder": offlineOrder,
        }
        return self.fyers.place_order(data)

    def modify_order(self, id, limitPrice=None, stopPrice=None, qty=None):
        """
        Modifies an existing order.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        data = {"id": id}
        if limitPrice is not None:
            data["limitPrice"] = limitPrice
        if stopPrice is not None:
            data["stopPrice"] = stopPrice
        if qty is not None:
            data["qty"] = qty
        return self.fyers.modify_order(data)

    def cancel_order(self, id):
        """
        Cancels an existing order.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        data = {"id": id}
        return self.fyers.cancel_order(data)

    def get_holdings(self):
        """
        Fetches the user's holdings.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        return self.fyers.holdings()

    def exit_positions(self, data=None):
        """
        Exits all open positions.
        """
        if not self.fyers:
            print("Access token not set. Please authenticate first.")
            return None
        return self.fyers.exit_positions(data)


if __name__ == '__main__':
    # Example usage
    fyers_api = FyersAPI()
    auth_code = fyers_api.generate_auth_code()
    fyers_api.set_access_token(auth_code)
    profile = fyers_api.get_profile()
    print(profile)

    # Example Websocket usage
    def onmessage(message):
        """
        Callback function to receive messages from Fyers Websocket
        """
        print("Response:", message)

    def onerror(message):
        """
        Callback function to receive messages from Fyers Websocket
        """
        print("Error:", message)

    def onclose(message):
        """
        Callback function to receive messages from Fyers Websocket
        """
        print("Connection closed:", message)

    def onopen():
        """
        Callback function to subscribe to data type and symbols upon connection open
        """
        data_type = "symbolData"
        symbols = ["NSE:NIFTY50-INDEX", "BSE:SENSEX"]
        fyers_api.fyers.subscribe(symbols=symbols, data_type=data_type)
        fyers_api.fyers.keep_running()

    # To be implemented in a separate thread
    # access_token = fyers_api.client_id + ':' + fyers_api.fyers.token
    # fyers_ws = fyersModel.FyersSocket(access_token=access_token, log_path="")
    # fyers_ws.on_message = onmessage
    # fyers_ws.on_error = onerror
    # fyers_ws.on_close = onclose
    # fyers_ws.on_open = onopen
    # fyers_ws.subscribe()

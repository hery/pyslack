import datetime
import logging
import requests


class SlackError(Exception):
    pass


class SlackClient(object):

    BASE_URL = 'https://slack.com/api'

    def __init__(self, token):
        self.token = token
        self.blocked_until = None

    def _make_request(self, method, params):
        """Make request to API endpoint

        Note: Ignoring SSL cert validation due to intermittent failures
        http://requests.readthedocs.org/en/latest/user/advanced/#ssl-cert-verification
        """
        if self.blocked_until is not None and \
                datetime.datetime.utcnow() < self.blocked_until:
            raise SlackError("Too many requests - wait until {0}" \
                    .format(self.blocked_until))

        url = "%s/%s" % (SlackClient.BASE_URL, method)
        params['token'] = self.token
        response = requests.post(url, data=params, verify=False)

        if response.status_code == 429:
            # Too many requests
            retry_after = int(response.headers.get('retry-after', '1'))
            self.blocked_until = datetime.datetime.utcnow() + \
                    datetime.timedelta(seconds=retry_after)
            raise SlackError("Too many requests - retry after {0} second(s)" \
                    .format(retry_after))

        result = response.json()
        if not result['ok']:
            raise SlackError(result['error'])
        return result

    def chat_post_message(self, channel, text, **params):
        """chat.postMessage

        This method posts a message to a channel.

        Check docs for all available **params options:
        https://api.slack.com/methods/chat.postMessage
        """
        method = 'chat.postMessage'
        params.update({
            'channel': channel,
            'text': text,
        })
        return self._make_request(method, params)

    def chat_update_message(self, channel, text, timestamp):
        """chat.update
        https://api.slack.com/methods/chat.update

        This method updates a message.

        Required parameters:
        `ts`:  Timestamp of the message to be updated (e.g: "1405894322.002768")    
        `channel`: Channel containing the message to be updated. (e.g: "C1234567890")
        `text`: New text for the message, using the default formatting rules. (e.g: "Hello world")
        """
        method = 'chat.update'
        params = {
            'channel': channel,
            'text': text,
            'ts': timestamp,
        }
        return self._make_request(method, params)


class SlackHandler(logging.Handler):
    """A logging handler that posts messages to a Slack channel!

    References:
    http://docs.python.org/2/library/logging.html#handler-objects
    """
    def __init__(self, token, channel, **kwargs):
        super(SlackHandler, self).__init__()
        self.client = SlackClient(token)
        self.channel = channel
        self._kwargs = kwargs

    def emit(self, record):
        message = self.format(record)
        self.client.chat_post_message(self.channel,
                                      message,
                                      **self._kwargs)

from six import string_types

from .exceptions import SlackError


class Slack(object):

    def __init__(self, app=None):
        self._commands = {}
        self.team_id = None

        if app:
            self.init_app(app)

    def init_app(self, app=None):
        """Initialize application configuration"""
        config = getattr(app, 'config', app)

        self.team_id = config.get('TEAM_ID')

    def command(self, command, token, team_id=None, methods=['GET'], **kwargs):
        """A decorator used to register a command.
        Example::

            @slack.command('your_command', token='your_token',
                           team_id='your_team_id', methods=['POST'])
            def your_method(**kwargs):
                text = kwargs.get('text')
                return slack.response(text)

        :param command: the command to register
        :param token: your command token provided by slack
        :param team_id: optional. your team_id provided by slack.
                        You can also specify the "TEAM_ID" in app
                        configuration file for one-team project
        :param methods: optional. HTTP methods which are accepted to
                        execute the command
        :param kwargs: optional. the optional arguments which will be passed
                       to your register method
        """
        if team_id is None:
            team_id = self.team_id
        if team_id is None:
            raise RuntimeError('TEAM_ID is not found in your configuration!')

        def deco(func):
            self._commands[(team_id, command)] = (func, token, methods, kwargs)
            return func
        return deco

    def dispatch(self):
        """Dispatch http request to registerd commands.
        Example::

            slack = Slack(app)
            app.add_url_rule('/', view_func=slack.dispatch)
        """
        from flask import request

        method = request.method

        data = request.args
        if method == 'POST':
            data = request.form

        token = data.get('token')
        team_id = data.get('team_id')
        command = data.get('command') or data.get('trigger_word')

        if isinstance(command, string_types):
            command = command.strip().lstrip('/')

        try:
            self.validate(command, token, team_id, method)
        except SlackError as e:
            return self.response(e.msg)

        func, _, _, kwargs = self._commands[(team_id, command)]
        kwargs.update(data.to_dict())

        return func(**kwargs)

    dispatch.methods = ['GET', 'POST']

    def validate(self, command, token, team_id, method):
        """Validate request queries with registerd commands

        :param command: command parameter from request
        :param token: token parameter from request
        :param team_id: team_id parameter from request
        :param method: the request method
        """
        if (team_id, command) not in self._commands:
            raise SlackError('Command {0} is not found in team {1}'.format(
                             command, team_id))

        func, _token, methods, kwargs = self._commands[(team_id, command)]

        if method not in methods:
            raise SlackError('{} request is not allowed'.format(method))

        if token != _token:
            raise SlackError('Your token {} is invalid'.format(token))

    def response(self, payload, content_type='text/plain; charset=utf-8'):
        """Return a response as:
            if text, just a string "hi, i'm slackbot"
            if json, payload can have the following values:
                "response_type" - "in_channel" or "ephemeral"
                "text" - see https://api.slack.com/docs/formatting
                "attachments" - see https://api.slack.com/docs/attachments
                
        :param payload: text or json returned to client
        """
        from flask import Response
        return Response(payload, content_type=content_type)

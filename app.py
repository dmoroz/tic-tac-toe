# -*- coding: utf-8  -*-

import logging
import os.path
import time

import tornado.escape
import tornado.gen
import tornado.ioloop
import tornado.template
import tornado.web
import tornado.websocket

from tornado.options import define, options
from tornado.web import URLSpec as url

from game import Game


PROJECT_ROOT = os.path.normpath(os.path.dirname(__file__))


define('port', default=3000, help='run on the given port', type=int)
define('address', default='0.0.0.0', help='run on the given address', type=str)


@tornado.gen.coroutine
def maybe_future(f, *args, **kwargs):
    result = f(*args, **kwargs)
    if isinstance(result, tornado.gen.Future):
        result = yield result
    raise tornado.gen.Return(result)


class Application(tornado.web.Application):
    """ Main application class """

    def __init__(self):

        handlers = [
            url(r'/', IndexHandler, name='index'),
            url(r'/play', GameStartHandler, name='game_start'),
            url(r'/game/(?P<game_hash>\w+)/socket', GameHandler, name='game'),
            url(r'/game/(?P<game_hash>\w+)', GameDetailHandler, name='game_detail'),
        ]

        settings = {
            'debug': True,
            'logging': logging.basicConfig(level=logging.INFO),
            'static_path': os.path.join(PROJECT_ROOT, 'assets'),
            'template_path': os.path.join(PROJECT_ROOT, 'templates'),
        }

        super(Application, self).__init__(handlers, **settings)


class IndexHandler(tornado.web.RequestHandler):
    """Index page handler"""

    def get(self):
        payload = {}
        self.render('base.html', **payload)


class GameStartHandler(tornado.web.RequestHandler):
    """
    Game start handler
    """

    @tornado.gen.coroutine
    def get(self):
        # Create a new game
        game = yield Game.create()
        self.redirect(self.reverse_url('game_detail', game.game_hash))


class GameDetailHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    def get(self, game_hash):

        game = yield Game.get(game_hash)

        # Get gamer hash either from cookie or create a new one
        if self.get_cookie('gamer_hash'):
            gamer_hash = self.get_cookie('gamer_hash')
        else:
            gamer_hash = game._get_random_hash()
            self.set_cookie('gamer_hash', gamer_hash)

        gamer = yield game.get_gamer(gamer_hash)

        payload = {
            'game': game.state,
            'gamer': gamer
        }
        self.render('game.html', **payload)


class GameHandler(tornado.websocket.WebSocketHandler):
    """WebSocket game handler"""

    ALLOWED_EVENTS = ('read', 'update')
    GAMER_MAP = {}

    def read(self, *args, **kwargs):
        """
        Reads current game state
        """

        self.write_message(
            tornado.escape.to_unicode(tornado.escape.json_encode(self.game.state))
        )

    @tornado.gen.coroutine
    def update(self, game_updated):
        """
        Updates coordinates, last mark and checks game status
        """

        self.game.state.update(game_updated)
        yield self.game.save()

        # Check game status
        start = time.time()
        yield self.game.status()
        logging.info('Game status updated in {:.2f}ms'.format((time.time() - start) * 1000))

        yield self.send_to_all(tornado.escape.to_unicode(
            tornado.escape.json_encode(self.game.state)
        ))

    @tornado.gen.coroutine
    def open(self, game_hash):
        """
        Handles WebSocket connection openning
        """

        logging.info('WebSocket opened')

        self.game = yield Game.get(game_hash)

        # Add empty set to gamers map in gamers attribute
        self.gamers = self.GAMER_MAP.setdefault(game_hash, set())

        # Add gamer to gamers set
        self.gamers.add(self)

        logging.info('Gamer added')
        logging.info('Gamers: {}'.format(len(self.gamers)))

    def send_to_all(self, message):
        """
        Send message to all gamers in the current game
        """

        logging.info('Sending to all message: {}'.format(message))

        for g in self.gamers:
            g.write_message(message)

    @tornado.gen.coroutine
    def on_message(self, message):
        """
        Emits event on message recieved from client
        """
        message = tornado.escape.json_decode(message)
        event, value = message.items()[0]

        if event not in self.ALLOWED_EVENTS:
            raise Exception('Method for {} event is not implemeneted.'.format(event))

        yield maybe_future(getattr(self, event), value)

    def on_close(self):
        logging.info("WebSocket closed")
        # Remove gamer from gamers set
        self.gamers.remove(self)
        logging.info('Gamer removed')
        logging.info('Gamers: {}'.format(len(self.gamers)))


def main():
    Game.setup_db()
    application = Application()
    application.listen(options.port, options.address)
    logging.info('Running on http://{0.address}:{0.port}'.format(options))
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()

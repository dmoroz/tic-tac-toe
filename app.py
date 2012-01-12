# -*- coding: utf-8  -*-

import logging
import os.path

import asyncmongo
import tornado.escape
import tornado.ioloop
import tornado.template
import tornado.web
import tornado.websocket
from tornado.options import define, options
from tornado.web import URLSpec as url

from game import (GameManager, generate_gamer_hash, generate_game_hash)


PROJECT_ROOT = os.path.normpath(os.path.dirname(__file__))
GAMER_MAP = {}
define('port', default=3000, help='run on the given port', type=int)
define('address', default='0.0.0.0', help='run on the given address', type=str)


class Application(tornado.web.Application):
    """ Main application class """

    def __init__(self):

        self.db = asyncmongo.Client(
            pool_id='gamedb',
            host='127.0.0.1',
            port=27017,
            dbname='tictactoe'
        )

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
    """Game start handler"""

    @tornado.web.asynchronous
    def get(self):
        # Create a new game
        self.game_manager = GameManager(
            generate_game_hash(self.request),
            self.application.db,
        )
        self.game_manager.create(self._on_insert)

    def _on_insert(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.game_manager.read(self._on_response)

    def _on_response(self, response, error):
        self.redirect(
            self.reverse_url('game_detail', response['_id'])
        )
    

class GameDetailHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    def get(self, game_hash):
        # Get gamer hash either from cookie or create a new one
        if self.get_cookie('gamer_hash'):
            gamer_hash = self.get_cookie('gamer_hash')
        else:
            gamer_hash = generate_gamer_hash(self.request)
            self.set_cookie('gamer_hash', gamer_hash)

        self.gamer_hash = gamer_hash

        self.game_manager = GameManager(
            game_hash,
            self.application.db
        )
        self.game_manager.read(self._on_find)

    def _on_find(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)

        gamer = self.game_manager.gamer(response, self.gamer_hash)

        payload = {
            'game': response,
            'gamer': u'%s' % gamer
        }

        self.render('game.html', **payload)


class GameHandler(tornado.websocket.WebSocketHandler):
    """WebSocket game handler"""

    def read(self, value=None):
        """ Reads current game state """
        self.game_manager.read(self._on_read)

    def _on_read(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)

        return self.write_message(tornado.escape.to_unicode(
            tornado.escape.json_encode(response)
        ))

    def update(self, game_updated):
        """Updates coordinates, last mark and checks game status"""
        self.game_manager.update(game_updated, self._on_update)
        # Check game status
        self.game_manager.status(game_updated)

    def _on_update(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.game_manager.read(self._on_read_after_update)

    def _on_read_after_update(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.send_to_all(tornado.escape.to_unicode(
            tornado.escape.json_encode(response)
        ))

    def open(self, game_hash):
        """Handles WebSocket connection openning"""
        logging.info('WebSocket opened')
        self.game_hash = game_hash
        self.game_manager = GameManager(
            self.game_hash,
            self.application.db
        )

        # Add empty set to gamers map in gamers attribute
        setattr(self, 'gamers', GAMER_MAP.setdefault(self.game_hash,
                                                     set()))
        # Add gamer to gamers set
        self.gamers.add(self)
        logging.info('Gamer added')
        logging.info('Gamers: %s' % len(self.gamers))

    def send_to_all(self, message):
        """Send message to all gamers in the current game"""
        for gamer in self.gamers:
            gamer.write_message(message)

    def on_message(self, message):
        """Emits event on message recieved from client"""
        message = tornado.escape.json_decode(message)
        event, value = message.items()[0]
        return self.emit_event(event, value)

    def on_close(self):
        logging.info("WebSocket closed")
        # Remove gamer from gamers set
        self.gamers.remove(self)
        logging.info('Gamer removed')
        logging.info('Gamers: %s' % len(self.gamers))

    event_list = (
        'read',
        'update',
    )

    def emit_event(self, event, value=None):
        if not event in self.event_list:
            raise Exception('Method for %s event is not implemeneted.' %
                            event)
        return getattr(self, event)(value)


def main():
    application = Application()
    application.listen(options.port, options.address)
    logging.info('Running on http://%s:%s' % (
        options.address,
        options.port
    ))
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()

# -*- coding: utf-8  -*-

import datetime
import hashlib
import hmac

from copy import deepcopy

import tornado.gen


__all__ = ('generate_gamer_hash', 'generate_game_hash', 'GameManager')


def generate_gamer_hash(request):
    """Generates gamer hash using hmac and md5"""
    return hmac.new('%s!@#%s$)^%s&*(' % (
        request.remote_ip,
        request.headers.get('User-Agent', 'Foofox'),
        hashlib.md5('%s' % datetime.datetime.now()).hexdigest()
    )).hexdigest()


def generate_game_hash(request):
    """Generates gamer hash using md5"""
    return hashlib.md5('%s%s' % (
        request.remote_ip,
        datetime.datetime.now()
    )).hexdigest()


WINNING_COMBINATIONS = (
    # Verticals
    {'a0', 'a1', 'a2'},
    {'b0', 'b1', 'b2'},
    {'c0', 'c1', 'c2'},
    # Horizontals
    {'a0', 'b0', 'c0'},
    {'a1', 'b1', 'c1'},
    {'a2', 'b2', 'c2'},
    # Diagonals
    {'a0', 'b1', 'c2'},
    {'a2', 'b1', 'c0'},
)


class GameManager(object):
    """ Game Manager object """

    def __init__(self, game_hash, db):
        self.game_hash = game_hash
        self.db = db

    def _grid(self):
        """
        Generates grid cells coordinates with empty values.
        """
        return {letter + str(index): None for letter in ['a', 'b', 'c'] for index in range(3)}

    @tornado.gen.coroutine
    def create(self):
        """
        Creates a new game
        """
        STATUS_CHOICES = {
            'new': 1,
            'game': 2,
            'finish': 3,
        }
        game_payload = {
            '_id': self.game_hash,
            'gamers': {
                'primary': None,
                'secondary': None,
            },
            'winner': None,
            'winning_combination': None,
            'draw': None,
            'coordinates': self._grid(),
            'last_mark': None,
            'status': STATUS_CHOICES.get('new'),
        }
        yield tornado.gen.Task(self.db.games.insert, game_payload)

    @tornado.gen.coroutine
    def read(self):
        """
        Reads an existent game
        """
        result = yield tornado.gen.Task(self.db.games.find_one, {'_id': self.game_hash})
        raise tornado.gen.Return(result.args[0])

    @tornado.gen.coroutine
    def update(self, game_updated):
        """
        Updates current game
        """
        result = yield tornado.gen.Task(
            self.db.games.update,
            {'_id': self.game_hash},
            game_updated
        )
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def _gamer_add(self, game, gamer_hash, gamer_role):
        """
        Adds a gamer to the current game with a given gamer_role.
        Argument gamer_role might be either `primary` or `secondary`
        """
        game_updated = deepcopy(game)
        game_updated['gamers'].update({gamer_role: gamer_hash})
        yield self.update(game_updated)

    @tornado.gen.coroutine
    def gamer(self, game, gamer_hash):
        """
        Handles a given gamer for a current game. Adding it either
        as primary or secondary. Returns 'primary' or 'secondary'
        respetively, to show how this gamer is handled.
        Returns 'hermit' if game already has 2 gamers.
        """

        # If game has no gamers
        if not any(game['gamers'].values()):
            # Add gamer as primary
            role = 'primary'
            yield self._gamer_add(game, gamer_hash, role)
            raise tornado.gen.Return(role)

        # If gamer participate this game
        if gamer_hash in game['gamers'].values():
            role = [key for key, value in game['gamers'].iteritems()
                    if value == gamer_hash][0]
            raise tornado.gen.Return(role)

        # If game has no secondary gamer
        if game['gamers']['secondary'] is None:
            # Add gamer as secondary
            role = 'secondary'
            yield self._gamer_add(game, gamer_hash, role)
            raise tornado.gen.Return(role)

        # If game already has 2 gamers and previous condition fails
        if all(game['gamers'].values()):
            role = 'hermit'
            raise tornado.gen.Return(role)

    def can_play(self, game, gamer_hash):
        """
        Checks whether a given gamer can participate in the current game
        """
        return gamer_hash in game['gamers'].values()

    def mark(self, game, gamer_hash):
        """
        Gets a mark for a current gamer
        """
        return 'cross' if game['gamers']['primary'] == gamer_hash else 'nought'

    @tornado.gen.coroutine
    def status(self, game):
        """
        Monitors status of the current game, checks for winning
        combinations and checks whether game result is draw.
        When game is finished, updates game state with appropriate values
        """

        result = None

        coordinates = game['coordinates']
        current_turn_mark = game['last_mark']
        current_turn_mark_coordinates = {coordinate
            for coordinate, mark in coordinates.iteritems()
            if mark == current_turn_mark}

        for combination in WINNING_COMBINATIONS:
            # Check whether winning combination presents in current turn mark coordiates
            if combination <= current_turn_mark_coordinates:
                result = {
                    'winning_combination': list(combination),
                    'winner': current_turn_mark
                }
                break
        else:
            # Check whether a game result is draw (no result and all coordinates are filled out)
            if all(coordinates.values()):
                result = {'draw': True}

        # Finish a game if there is a result
        if result:
            game_updated = deepcopy(game)
            game_updated.update({
                'winner': result.get('winner'),
                'winning_combination': result.get('winning_combination'),
                'draw': result.get('draw'),
                # Set status to `finish` (3)
                'status': 3,
            })
            yield self.update(game_updated)

# coding: utf-8

import hashlib
import time
import uuid

import tornado.gen

import asyncmongo


__all__ = ('Game',)


class Game(object):
    """
    Game model object class
    """

    STATUS_CHOICES = {
        'new': 1,
        'game': 2,
        'finish': 3,
    }

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

    db = None
    state = None

    def __init__(self, game_hash=None):
        assert self.db is not None, 'DB is not set'
        self.game_hash = game_hash

    @classmethod
    def setup_db(cls):
        cls.db = asyncmongo.Client(
            pool_id='gamedb',
            host='127.0.0.1',
            port=27017,
            dbname='tictactoe'
        )

    @classmethod
    @tornado.gen.coroutine
    def get(cls, game_hash):
        game = cls(game_hash)
        game.state = yield game.read()
        raise tornado.gen.Return(game)

    @classmethod
    @tornado.gen.coroutine
    def create(cls):
        """
        Creates a new game and returns it's object.
        """

        game = cls()
        game.game_hash = game._get_random_hash()

        game.state = {
            '_id': game.game_hash,
            'gamers': {
                'primary': None,
                'secondary': None,
            },
            'winner': None,
            'winning_combination': None,
            'draw': None,
            'coordinates': game._get_empty_grid(),
            'last_mark': None,
            'status': game.STATUS_CHOICES.get('new'),
        }

        yield tornado.gen.Task(game.db.games.insert, game.state)

        raise tornado.gen.Return(game)

    @tornado.gen.coroutine
    def read(self):
        """
        Reads an existent game
        """
        result = yield tornado.gen.Task(self.db.games.find_one, {'_id': self.game_hash})
        raise tornado.gen.Return(result.args[0])

    @tornado.gen.coroutine
    def save(self):
        """
        Persists current game state.
        """
        result = yield tornado.gen.Task(self.db.games.update, {'_id': self.game_hash}, self.state)
        raise tornado.gen.Return(result)

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
    def get_gamer(self, gamer_hash):
        """
        Handles a given gamer for a current game. Adding it either
        as primary or secondary. Returns 'primary' or 'secondary'
        respetively, to show how this gamer is handled.
        Returns 'hermit' if game already has 2 gamers.
        """

        # If game has no gamers
        if not any(self.state['gamers'].values()):
            # Add gamer as primary
            role = 'primary'
            self.state['gamers'].update({role: gamer_hash})
            yield self.save()
            raise tornado.gen.Return(role)

        # If gamer participate this game
        if gamer_hash in self.state['gamers'].values():
            role = [key for key, value in self.state['gamers'].iteritems()
                    if value == gamer_hash][0]
            raise tornado.gen.Return(role)

        # If game has no secondary gamer
        if self.state['gamers']['secondary'] is None:
            # Add gamer as secondary
            role = 'secondary'
            self.state['gamers'].update({role: gamer_hash})
            yield self.save()
            raise tornado.gen.Return(role)

        # If game already has 2 gamers and previous condition fails
        if all(self.state['gamers'].values()):
            role = 'hermit'
            raise tornado.gen.Return(role)

    @tornado.gen.coroutine
    def status(self):
        """
        Monitors status of the current game, checks for winning
        combinations and checks whether game result is draw.
        When game is finished, updates game state with appropriate values.
        """

        result = None

        coordinates = self.state['coordinates']
        current_turn_mark = self.state['last_mark']
        current_turn_mark_coordinates = {coordinate
            for coordinate, mark in coordinates.iteritems()
            if mark == current_turn_mark}

        for combination in self.WINNING_COMBINATIONS:
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
            self.state.update({
                'winner': result.get('winner'),
                'winning_combination': result.get('winning_combination'),
                'draw': result.get('draw'),
                'status': self.STATUS_CHOICES['finish'],
            })
            yield self.save()

    def _get_random_hash(self):
        """
        Generates and returns a random hash.
        """
        return hashlib.sha256(str(time.time())).hexdigest() + uuid.uuid4().hex

    def _get_empty_grid(self):
        """
        Generates grid cells coordinates with empty values and returns as a dictionary.
        """
        return {letter + str(index): None for letter in ['a', 'b', 'c'] for index in range(3)}

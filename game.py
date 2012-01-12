# -*- coding: utf-8  -*-

import datetime
import hashlib
import hmac
from copy import deepcopy


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


class GameManager(object):
    """ Game Manager object """

    def __init__(self, game_hash, db):
        self.game_hash = game_hash
        self.db = db

    def _grid(self):
        """Generates grid cells coordinates"""
        coordinates = {}
        for l in 'abc':
            for d in '012':
                coordinates[l + d] = None
        return coordinates

    def create(self, callback):
        """Creates a new game"""
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
        self.db.games.insert(game_payload, callback=callback)

    def read(self, callback):
        """Reads an existent game"""
        self.db.games.find_one(
            {'_id': self.game_hash},
            callback=callback
        )

    def update(self, game_updated, callback):
        """Updates current game"""
        self.db.games.update({'_id': self.game_hash},
                             game_updated,
                             callback=callback)

    def _gamer_add(self, game, gamer_hash, gamer_role, callback):
        """
        Adds a gamer to the current game with a given gamer_role.
        Argument gamer_role might be either `primary` or `secondary`
        """
        game_updated = deepcopy(game)
        game_updated['gamers'].update({gamer_role: gamer_hash})
        self.update(game_updated, callback)

    def _on_gamer_add(self, response, error):
        pass

    def actions(self, actions, game, gamer_hash):
        """Emits some game related actions, listen in actions list"""
        return (
            getattr(self, action)(game, gamer_hash)
            for action in actions
        )

    def gamer(self, game, gamer_hash):
        """
        Handles a given gamer for a current game. Adding it either
        as primary or secondary. Returns 'primary' or 'secondary'
        respetively, to show how this gamer is handled.
        Returns 'hermit' if game already has 2 gamers.
        """

        result = u'%s'

        # If game has no gamers
        if not any(game['gamers'].values()):
            # Add gamer as primary
            role = 'primary'
            self._gamer_add(game, gamer_hash, role, self._on_gamer_add)
            return result % role

        # If gamer participate this game
        if gamer_hash in game['gamers'].values():
            return (
                result % key
                for key, value in game['gamers'].iteritems()
                if value == gamer_hash
            ).next()

        # If game has no secondary gamer
        if game['gamers']['secondary'] is None:
            # Add gamer as secondary
            role = 'secondary'
            self._gamer_add(game, gamer_hash, role, self._on_gamer_add)
            return result % role

        # If game already has 2 gamers and previous condition fails
        if all(game['gamers'].values()):
            return result % 'hermit'

    def can_play(self, game, gamer_hash):
        """
        Checks whether a given gamer can participate in the current game
        """
        if gamer_hash in game['gamers'].values(): return True

    def mark(self, game, gamer_hash):
        """Gets a mark for a current gamer"""
        mark = u'%s'
        return (
            mark % 'cross'
            if game['gamers']['primary'] == gamer_hash
            else 'nought'
        )

    def status(self, game):
        """
        Monitors status of the current game, checks for winning
        combinations and checks whether game result is draw.
        When game is finished, updates game state with appropriate values
        """

        result = None

        WINNING_COMBINATIONS = (
            # Verticals
            ('a0', 'a1', 'a2'),
            ('b0', 'b1', 'b2'),
            ('c0', 'c1', 'c2'),
            # Horizontals
            ('a0', 'b0', 'c0'),
            ('a1', 'b1', 'c1'),
            ('a2', 'b2', 'c2'),
            # Diagonals
            ('a0', 'b1', 'c2'),
            ('a2', 'b1', 'c0'),
        )

        MARKS = ('cross', 'nought')

        coordinates = game.get('coordinates')
        
        # Create winning combination values maps
        for combination in WINNING_COMBINATIONS:
            combination_map = {}
            for key, value in coordinates.iteritems():
                if key in combination:
                    combination_map[key] = value
            
            # Check for a winning combination
            for mark in MARKS:
                mark_count = combination_map.values().count(mark)
                if mark_count == 3:
                    result = {
                        'winning_combination': combination_map.keys(),
                        'winner': mark,
                    }

            # Check if a game result is draw
            if all(coordinates.values()):
                result = {'draw': True}

        print(result)

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
            print(game_updated)
            self.update(game_updated, self._on_gamer_add)

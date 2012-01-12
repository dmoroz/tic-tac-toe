/*
  * Tic-Tac-Toe Game Client v0.1alpha
  * Copyright 2012, Dima Moroz
  * http://dimamoroz.com
  *
  * Includes:
  *  JQuery
  *  http://jquery.com/
  *
  *  JQuery Template
  *  http://api.jquery.com/jQuery.template/
  *
  *  Backbone.js
  *  http://documentcloud.github.com/backbone/
  *
  *  Underscore.js
  *  http://documentcloud.github.com/underscore/
  *
  *  JSON in JavaScript (json2.js)
  *  https://github.com/douglascrockford/JSON-js
  *
  *  Gritter
  *  http://boedesign.com/blog/2009/07/11/growl-for-jquery-gritter/
*/



// Redirect to wiki page wth supported browsers,
// if there is no WebSocket support in the browser
if (!window.WebSocket) {
  alert('Your browser does not support WebSocket.');
  window.location = 'http://en.wikipedia.org/wiki/WebSocket#Browser_support';
}

// Create websocket connection
window.ws = new WebSocket(document.location.href.replace('http', 'ws') + '/socket');

$(function() {

  var WebSocketSync = function(method, model, options) {
    var ws = window.ws;

    function send(msg) {
      return JSON.stringify(msg);
    }

    function onmessage(msg) {
      var data = JSON.parse(msg.data);
      if (data) {
        options.success(data);
      } else {
        options.error('Something went wrong!');
      }
    };
    
    function read() {
      ws.onopen = function() {
        ws.send(send({read: null}));
      }
      ws.onmessage = onmessage;
    };

    function update() {
      ws.send(send({update: model}));
      ws.onmessage = onmessage;
    };

    switch (method) {
      case 'read':
        read();
        break;
      case 'update':
        update();
        break;
    };
  };

  var Grid = Backbone.Model.extend({
    sync: WebSocketSync,
    initialize: function() {
      this.id = game_hash;
      this.fetch({
        success: function(data) {
          // Render Grid
          gridview.render(data);
        },
      });
    },
  });

  window.grid = new Grid;
  
  // Bind model change event
  // TODO: automate this event further
  grid.bind('change', function() {
    // Update grid view
    gridview.render(grid);
    
    // Check if a game result is draw
    if (grid.hasChanged('draw') && grid.get('draw')) {
      gridview.notify('Draw!');
    }

    // Check if there's a winner
    if (grid.hasChanged('winner')) {
      // Hilight winning combination cells
      gridview.highlight_winning_combination(
        grid.get('winning_combination'),
        grid.get('winner')
      );
      // Notify gamers
      if (grid.get('winner') === mark) {
        var notification = 'You have won!';
      } else {
        var notification = 'You have lost!';
      }
      gridview.notify(notification);
    }
    // Check whos turn it is now and notify gamers
    if (grid.hasChanged('last_mark')) {
      if (grid.get('status') === 3) {
        return;
      }
      if (grid.get('last_mark') !== mark) {
        var notification = 'Your turn!';
      } else {
        var notification = 'Your opponent turn!';
      }
      gridview.notify(notification);
    }
    // If game is new, notify gamers whos turn it is now
    // FIXME DRY it
    else if (grid.get('status') === 1) {
      if (mark === 'cross') {
        var notification = 'Your turn!';
      } else {
        var notification = 'Your opponent turn!';
      }
      gridview.notify(notification);
    }

  });

  var GridView = Backbone.View.extend({
    el: '#grid',

    events: {
      'click .cell': 'render_mark',
    },

    highlight_winning_combination: function(combination, mark) {
      $.each(combination, function(index, coordinate) {
        $('.' + coordinate).parent().addClass(mark + '-highlighted');
      });
    },

    notify: function(text) {
      // Notification using Gritter
      $.gritter.add({
        title: 'Notification:',
        text: text,
        time: 3000,
      });
    },

    render_mark: function(eve) {
      var targetElement = $(eve.currentTarget).children();

      // Check if game is finished
      if (grid.get('status') === 3) {
        this.notify('This game is finished!');
        return;
      }

      // Check if it is the first turn
      // Statuses are: new = 1, game = 2, finish = 3
      // Turn is not allowed If status is new and mark is nought
      if (grid.get('status') !== 2 && mark === 'nought') {
        this.notify('Cross player should make a first turn!');
        return;
      }

      // Check the last rendered mark
      if (grid.get('last_mark') === mark) {
        this.notify('It is not your turn!');
        return;
      }

      // Check if cell is not marked
      if (targetElement.children().size() > 0) {
        this.notify('Already marked!');
        return;
      }

      // Update coordinates and last rendered mark
      var coordinate = targetElement.attr('class');
      var coordinates = grid.get('coordinates');
      coordinates[coordinate] = mark;

      // Update status also, if game is new
      var game_status = grid.get('status');
      if (game_status === 1) {
        // Set game status to `game` (2)
        game_status = 2;
      }
      grid.save({
        coordinates: coordinates,
        last_mark: mark,
        status: game_status
      });
    
      // Render mark within a target cell
      var markview = new MarkView({
        el: targetElement,
        type: mark,
      });
      markview.render();
    },

    render: function(data) {
      // Grid can be only rendered after model successfully fetched
      $.each(data.get('coordinates'), function(coordinate, mark) {
        if (mark) {
          var markview = new MarkView({
            el: $('.' + coordinate),
            type: mark,
          });
          markview.render();
        }
      });
    },
  });

  window.gridview = new GridView;

  var MarkView = Backbone.View.extend({
    initialize: function(params) {
      this.template = '#' + params.type + '-template';
    },
    render: function() {
        $(this.el).html($(this.template).tmpl());
    },
  });

});

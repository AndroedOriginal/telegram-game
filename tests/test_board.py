from bot.game.board import Position, cell_color, chebyshev_distance, is_adjacent


def test_a1_is_black_and_h1_is_white():
    assert cell_color(Position.from_algebraic("A1")) == "black"
    assert cell_color(Position.from_algebraic("H1")) == "white"


def test_a8_is_white_matching_spec_diagram():
    # Spec diagram row 8 (top) starts with a white cell at column A.
    assert cell_color(Position.from_algebraic("A8")) == "white"
    assert cell_color(Position.from_algebraic("B8")) == "black"


def test_algebraic_roundtrip():
    pos = Position(3, 5)
    assert pos.to_algebraic() == "D5"
    assert Position.from_algebraic("D5") == pos


def test_in_bounds():
    assert Position(0, 1).in_bounds()
    assert Position(7, 8).in_bounds()
    assert not Position(-1, 1).in_bounds()
    assert not Position(8, 1).in_bounds()
    assert not Position(0, 0).in_bounds()
    assert not Position(0, 9).in_bounds()


def test_adjacency():
    center = Position(4, 4)
    assert is_adjacent(center, Position(4, 5))
    assert is_adjacent(center, Position(5, 5))
    assert not is_adjacent(center, Position(6, 4))
    assert not is_adjacent(center, center)
    assert chebyshev_distance(center, Position(6, 6)) == 2

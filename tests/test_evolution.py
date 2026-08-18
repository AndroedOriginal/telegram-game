from bot.game.board import Position
from bot.game.evolution import can_use_spawn, evolution_announcement, evolve_player, mark_spawn_used
from bot.game.models import PieceType, Player, Spawn


def make_player(user_id=1, piece_type=PieceType.PAWN):
    return Player(user_id=user_id, username="alice", display_name="Alice", piece_type=piece_type)


def test_owner_cannot_use_own_unactivated_spawn():
    player = make_player(user_id=1)
    spawn = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=False)
    assert can_use_spawn(player, spawn) is False


def test_other_player_can_always_use_a_spawn():
    player = make_player(user_id=2)
    spawn = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=False)
    assert can_use_spawn(player, spawn) is True


def test_owner_can_use_spawn_once_activated_by_another():
    player = make_player(user_id=1)
    spawn = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=True)
    assert can_use_spawn(player, spawn) is True


def test_mark_spawn_used_activates_only_for_non_owner():
    owner = make_player(user_id=1)
    spawn = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=False)

    mark_spawn_used(owner, spawn)
    assert spawn.activated_by_other is False  # owner using it does not self-activate

    other = make_player(user_id=2)
    mark_spawn_used(other, spawn)
    assert spawn.activated_by_other is True


def test_evolving_on_foreign_spawn_unlocks_own_spawn():
    owner = make_player(user_id=1)
    own = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=False)
    foreign = Spawn(owner_user_id=2, position=Position(3, 4), activated_by_other=False)

    mark_spawn_used(owner, foreign, [own, foreign])

    assert foreign.activated_by_other is True
    assert own.activated_by_other is True
    assert can_use_spawn(owner, own) is True


def test_unlock_is_tied_to_owner_not_coordinate():
    owner = make_player(user_id=1)
    own = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=False)
    foreign = Spawn(owner_user_id=2, position=Position(3, 4), activated_by_other=False)
    mark_spawn_used(owner, foreign, [own, foreign])

    old = own.position
    own.position = Position(7, 7)
    assert can_use_spawn(owner, own) is True

    leftover = Spawn(owner_user_id=1, position=old, activated_by_other=False)
    assert can_use_spawn(owner, leftover) is False


def test_mark_spawn_used_is_permanent():
    owner = make_player(user_id=1)
    other = make_player(user_id=2)
    spawn = Spawn(owner_user_id=1, position=Position(0, 1), activated_by_other=True)
    mark_spawn_used(owner, spawn)  # should stay True, no reset logic exists
    assert spawn.activated_by_other is True
    mark_spawn_used(other, spawn)
    assert spawn.activated_by_other is True


def test_evolve_player_advances_through_full_order():
    player = make_player(piece_type=PieceType.PAWN)
    assert evolve_player(player) is True
    assert player.piece_type == PieceType.BISHOP
    assert evolve_player(player) is True
    assert player.piece_type == PieceType.KNIGHT
    assert evolve_player(player) is True
    assert player.piece_type == PieceType.ROOK
    assert evolve_player(player) is True
    assert player.piece_type == PieceType.QUEEN


def test_queen_cannot_evolve_further():
    player = make_player(piece_type=PieceType.QUEEN)
    assert evolve_player(player) is False
    assert player.piece_type == PieceType.QUEEN


def test_evolution_announcement_text():
    player = make_player(piece_type=PieceType.BISHOP)
    assert evolution_announcement(player) == "\U0001f508 @alice меняет фигуру на слона."

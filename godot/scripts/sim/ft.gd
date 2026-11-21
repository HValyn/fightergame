## Shared constants and enums for the fighting simulation.
## The simulation (scripts/sim) is pure logic: no Nodes, no rendering, no
## real-time clock. One call to MatchSim.step() == one 60 FPS frame.
class_name FT
extends RefCounted

const SCREEN_W := 1200
const SCREEN_H := 700
const GROUND_Y := 550.0
const FPS := 60

const INPUT_HISTORY := 15
const INPUT_BUFFER_FRAMES := 10        # an early press is remembered this long
const COMBO_DECAY_WINDOW := 40
const COMBO_SCALING_STEP := 0.08
const MIN_COMBO_SCALING := 0.3
const MAX_SUPER_METER := 100
const ROUND_TIME_SECONDS := 99
const ROUNDS_TO_WIN := 2
const ROUND_INTRO_FRAMES := 60
const ROUND_OUTRO_FRAMES := 120

enum State {
	IDLE, WALK_FORWARD, WALK_BACKWARD, JUMP, CROUCH,
	ATTACK_STARTUP, ATTACK_ACTIVE, ATTACK_RECOVERY,
	HITSTUN, BLOCKSTUN, KNOCKDOWN, DASH_FORWARD, DASH_BACKWARD,
}

enum Height { HIGH, MID, LOW, OVERHEAD }
enum MoveType { NORMAL, COMMAND_NORMAL, SPECIAL, SUPER, THROW }
enum Motion { NONE, QCF, QCB, DPF, DPB, HCF, HCB, CHARGE_BACK, CHARGE_DOWN, DOUBLE_QCF, ZIGZAG }

## Result of one attack meeting one defender.
enum HitResult { WHIFF, HIT, BLOCK, ARMOR }

const HEIGHT_NAMES := {"high": Height.HIGH, "mid": Height.MID, "low": Height.LOW, "overhead": Height.OVERHEAD}
const MOVE_TYPE_NAMES := {
	"normal": MoveType.NORMAL, "command_normal": MoveType.COMMAND_NORMAL,
	"special": MoveType.SPECIAL, "super": MoveType.SUPER, "throw": MoveType.THROW,
}
const MOTION_NAMES := {
	"none": Motion.NONE, "qcf": Motion.QCF, "qcb": Motion.QCB, "dpf": Motion.DPF, "dpb": Motion.DPB,
	"hcf": Motion.HCF, "hcb": Motion.HCB, "charge_back": Motion.CHARGE_BACK,
	"charge_down": Motion.CHARGE_DOWN, "double_qcf": Motion.DOUBLE_QCF, "zigzag": Motion.ZIGZAG,
}

static func state_name(s: int) -> String:
	return State.keys()[s]

static func actionable(s: int) -> bool:
	return s in [State.IDLE, State.WALK_FORWARD, State.WALK_BACKWARD, State.JUMP, State.CROUCH]

static func attacking(s: int) -> bool:
	return s in [State.ATTACK_STARTUP, State.ATTACK_ACTIVE, State.ATTACK_RECOVERY]

static func stunned(s: int) -> bool:
	return s in [State.HITSTUN, State.KNOCKDOWN]

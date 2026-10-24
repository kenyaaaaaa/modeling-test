extends Node2D
## Clock golem cut out of the front concept, animated MapleStory-style (held
## poses). The AnimationPlayer runs idle and attack; the clock ticks here.

## Emitted on the frame the arms hit the ground (deal damage, shake the camera).
signal attack_hit

## Where the hands point in the picture (degrees clockwise from 12).
const MINUTE_DRAWN := 57.0
const HOUR_DRAWN := 4.75

## Minute-hand ticks per second, and degrees per tick.
@export var ticks_per_second := 2.0
@export var degrees_per_tick := 6.0
## Time on the dial at the start, in minutes after 12 (9.5 = as drawn).
@export var start_minutes := 9.5

@onready var _player: AnimationPlayer = $AnimationPlayer
@onready var _minute: Node2D = $Body/HandMinute
@onready var _hour: Node2D = $Body/HandHour
var _time := 0.0


func _ready() -> void:
	_player.animation_finished.connect(_on_animation_finished)


## Ground slam. Does nothing if one is already under way.
func attack() -> void:
	if _player.current_animation != "attack":
		_player.play("attack")


func is_attacking() -> bool:
	return _player.current_animation == "attack"


func _on_animation_finished(anim: StringName) -> void:
	if anim == &"attack":
		_player.play("idle")


## Called by the attack animation on the hit frame.
func _on_attack_hit() -> void:
	attack_hit.emit()


func _process(delta: float) -> void:
	_time += delta
	var ticks := floorf(_time * ticks_per_second)
	# each tick overshoots a little and settles
	var since := _time * ticks_per_second - ticks
	var kick := sin(minf(since * 6.0, PI)) * 0.25 * exp(-since * 6.0)
	var minutes := start_minutes + (ticks + kick) * degrees_per_tick / 6.0
	_minute.rotation = deg_to_rad(fmod(minutes * 6.0, 360.0) - MINUTE_DRAWN)
	_hour.rotation = deg_to_rad(fmod(minutes * 0.5, 360.0) - HOUR_DRAWN)

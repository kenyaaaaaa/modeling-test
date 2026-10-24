extends Node2D
## Demo: Space / Enter / click to attack; the camera shakes on the hit.
## Run with `-- --auto` to attack on its own every few seconds.

@export var shake_strength := 7.0
@export var shake_time := 0.3
@export var auto_every := 3.5

@onready var _golem := $Golem2D
@onready var _camera: Camera2D = $Camera2D
var _shake := 0.0
var _auto := false
var _next := 1.2


func _ready() -> void:
	_golem.attack_hit.connect(func() -> void: _shake = shake_time)
	_auto = "--auto" in OS.get_cmdline_user_args()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept") or (event is InputEventMouseButton and event.pressed):
		_golem.attack()


func _process(delta: float) -> void:
	if _auto:
		_next -= delta
		if _next <= 0.0:
			_golem.attack()
			_next = auto_every
	# held-pose shake: jump to a new offset every other frame, fading out
	if _shake > 0.0:
		_shake -= delta
		if Engine.get_process_frames() % 2 == 0:
			var k := maxf(_shake / shake_time, 0.0)
			_camera.offset = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * shake_strength * k
	else:
		_camera.offset = Vector2.ZERO

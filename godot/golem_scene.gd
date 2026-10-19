extends Node3D
## Puts the toon and outline materials on the imported golem and plays idle.

const TOON := preload("res://shaders/toon.gdshader")
const TOON_GLASS := preload("res://shaders/toon_glass.gdshader")
const OUTLINE := preload("res://shaders/outline.gdshader")

## Per glTF material name: rim on metal, glow, transparency.
const LOOKS := {
	"brass": {"rim": 1.0},
	"brass_dark": {"rim": 0.5},
	"glass": {"alpha": 0.35},
	"sand_glow": {"emission": Color(0.9, 0.85, 0.5)},
}

@export var outline_thickness := 0.008

func _ready() -> void:
	# glTF: the golem faces +Z; view it from its front right like the sheet's 3/4 view
	$Camera3D.look_at_from_position(Vector3(-3.2, 2.3, 6.2), Vector3(0, 1.75, 0))
	$Sun.look_at_from_position(Vector3(-4, 6, 6), Vector3.ZERO)
	for mi in find_children("*", "MeshInstance3D", true, false):
		_restyle(mi as MeshInstance3D)
	var player := find_child("AnimationPlayer", true, false) as AnimationPlayer
	if player and player.has_animation("idle"):
		player.get_animation("idle").loop_mode = Animation.LOOP_LINEAR
		player.play("idle")

func _restyle(mi: MeshInstance3D) -> void:
	var outline := ShaderMaterial.new()
	outline.shader = OUTLINE
	outline.set_shader_parameter("thickness", outline_thickness)
	for i in mi.mesh.get_surface_count():
		var src := mi.mesh.surface_get_material(i) as BaseMaterial3D
		var look: Dictionary = LOOKS.get(src.resource_name, {}) if src else {}
		var toon := ShaderMaterial.new()
		toon.shader = TOON_GLASS if look.has("alpha") else TOON
		if src:
			toon.set_shader_parameter("albedo", src.albedo_color)
			if src.albedo_texture:
				toon.set_shader_parameter("albedo_texture", src.albedo_texture)
				toon.set_shader_parameter("use_texture", true)
		toon.set_shader_parameter("rim_amount", look.get("rim", 0.0))
		if look.has("emission"):
			var e: Color = look["emission"]
			toon.set_shader_parameter("emission", Vector3(e.r, e.g, e.b))
		if look.has("alpha"):
			toon.set_shader_parameter("alpha", look["alpha"])
		else:
			toon.next_pass = outline  # no hull around the glass
		mi.set_surface_override_material(i, toon)

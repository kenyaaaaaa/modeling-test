extends SceneTree
## godot --headless --path godot2d --script res://tools/check.gd
## Loads the scene and reports its parts and animations.

func _init() -> void:
	var scene := (load("res://golem2d.tscn") as PackedScene).instantiate()
	root.add_child(scene)
	await process_frame
	var player := scene.get_node("AnimationPlayer") as AnimationPlayer
	var idle := player.get_animation("idle")
	var missing := []
	for i in idle.get_track_count():
		var path := idle.track_get_path(i)
		if scene.get_node_or_null(NodePath(path.get_concatenated_names())) == null:
			missing.append(str(path))
	var report := {
		"sprites": scene.find_children("*", "Sprite2D", true, false).size(),
		"particles": scene.find_children("*", "CPUParticles2D", true, false).size(),
		"animations": player.get_animation_list(),
		"idle_length": idle.length,
		"tracks": idle.get_track_count(),
		"missing_tracks": missing,
		"playing": player.current_animation,
	}
	print("GOLEM2D_CHECK ", JSON.stringify(report))
	quit(1 if missing.size() > 0 else 0)

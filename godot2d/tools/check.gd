extends SceneTree
## godot --headless --path godot2d --script res://tools/check.gd
## Loads the scene and reports its parts and animations; fails if a track
## points at a node that isn't there.

func _init() -> void:
	var scene := (load("res://golem2d.tscn") as PackedScene).instantiate()
	root.add_child(scene)
	await process_frame
	var player := scene.get_node("AnimationPlayer") as AnimationPlayer
	var missing := []
	var tracks := {}
	for anim_name in player.get_animation_list():
		var anim := player.get_animation(anim_name)
		tracks[anim_name] = anim.get_track_count()
		for i in anim.get_track_count():
			var path := anim.track_get_path(i)
			var target := scene.get_node_or_null(NodePath(path.get_concatenated_names()))
			if target == null:
				missing.append("%s: %s" % [anim_name, path])
			elif anim.track_get_type(i) == Animation.TYPE_VALUE and not (path.get_concatenated_subnames() in target):
				missing.append("%s: %s (no property)" % [anim_name, path])
	var report := {
		"sprites": scene.find_children("*", "Sprite2D", true, false).size(),
		"particles": scene.find_children("*", "CPUParticles2D", true, false).size(),
		"tracks": tracks,
		"attack_length": player.get_animation("attack").length,
		"missing_tracks": missing,
		"playing": player.current_animation,
	}
	print("GOLEM2D_CHECK ", JSON.stringify(report))
	quit(1 if missing.size() > 0 else 0)

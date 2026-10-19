extends SceneTree
## godot --headless --path godot --script res://tools/check.gd
## Loads the scene, reports what Godot made of the glb, and (with a display)
## saves a screenshot: --shot=res://shot.png

func _init() -> void:
	var scene := (load("res://golem_scene.tscn") as PackedScene).instantiate()
	root.add_child(scene)
	await process_frame
	var meshes := 0
	var surfaces := 0
	var tris := 0
	for mi in scene.find_children("*", "MeshInstance3D", true, false):
		meshes += 1
		var m: Mesh = (mi as MeshInstance3D).mesh
		surfaces += m.get_surface_count()
		for i in m.get_surface_count():
			var idx: PackedInt32Array = m.surface_get_arrays(i)[Mesh.ARRAY_INDEX]
			tris += idx.size() / 3
	var skel := scene.find_child("Skeleton3D", true, false) as Skeleton3D
	var player := scene.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var report := {
		"meshes": meshes, "surfaces": surfaces, "triangles": tris,
		"bones": skel.get_bone_count() if skel else 0,
		"animations": player.get_animation_list() if player else [],
		"playing": player.current_animation if player else "",
	}
	print("GOLEM_CHECK ", JSON.stringify(report))
	var shot := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			shot = a.substr(7)
		if a.begins_with("--only="):   # debug: show one material only
			var keep := a.substr(7)
			for mi in scene.find_children("*", "MeshInstance3D", true, false):
				var m: Mesh = (mi as MeshInstance3D).mesh
				for i in m.get_surface_count():
					var src := m.surface_get_material(i)
					if not src or src.resource_name != keep:
						var hide := StandardMaterial3D.new()
						hide.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
						hide.albedo_color = Color(1, 1, 1, 0)
						(mi as MeshInstance3D).set_surface_override_material(i, hide)
		if a.begins_with("--at="):   # pose at this time of the idle loop
			var p := scene.find_child("AnimationPlayer", true, false) as AnimationPlayer
			p.seek(float(a.substr(5)), true)
			p.pause()
		if a == "--close":   # close-up of the clock
			(scene.get_node("Camera3D") as Camera3D).look_at_from_position(Vector3(-0.4, 3.1, 2.0), Vector3(0, 3.0, 0.6))
	if shot != "" and DisplayServer.get_name() != "headless":
		for i in 30:
			await process_frame
		root.get_texture().get_image().save_png(shot)
		print("GOLEM_SHOT ", shot)
	quit()

// Ink outline: the back faces pushed out along the normal (inverted hull).
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_opaque;

uniform vec4 line_color : source_color = vec4(0.05, 0.04, 0.04, 1.0);
uniform float thickness = 0.008;

void vertex() {
	VERTEX += NORMAL * thickness;
}

void fragment() {
	ALBEDO = line_color.rgb;
}

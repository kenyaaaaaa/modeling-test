// Glass variant (writes ALPHA, so it is drawn in the transparent pass).
// Toon look of the concept sheet: three flat bands of light, ink lines from
// the vertex colour (dark on cracks and rock borders), a bright rim on brass.
shader_type spatial;
render_mode diffuse_toon, specular_disabled;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_texture : source_color, filter_linear_mipmap;
uniform bool use_texture = false;
uniform float rim_amount : hint_range(0.0, 1.0) = 0.0;
uniform vec4 rim_color : source_color = vec4(1.0, 0.93, 0.7, 1.0);
uniform vec3 emission = vec3(0.0);
uniform float alpha : hint_range(0.0, 1.0) = 0.35;
uniform vec3 shadow_tint : source_color = vec3(0.52, 0.52, 0.58);
uniform vec3 mid_tint : source_color = vec3(0.78, 0.78, 0.82);

void fragment() {
	vec4 base = albedo;
	if (use_texture) {
		base *= texture(albedo_texture, UV);
	}
	ALBEDO = base.rgb * COLOR.rgb;
	EMISSION = emission;
	ALPHA = alpha;
	float facing = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	EMISSION += rim_color.rgb * step(0.62, facing) * rim_amount * 0.35;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	vec3 band = ndl > 0.25 ? vec3(1.0) : (ndl > -0.1 ? mid_tint : shadow_tint);
	DIFFUSE_LIGHT += band * LIGHT_COLOR * ATTENUATION / PI;
}

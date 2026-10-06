/*
 * Framework-owned audio presentation mods, available to every game.
 *
 * CD audio smoothing: each new XA / CD-DA stream starts with an empty SPU CD
 * input FIFO, so the first late sector starves it and the mix steps to zero
 * for a few milliseconds -- the click heard once per new video or speech
 * clip, on DuckStation as well. The manifest in mods/builtin/packages targets
 * game_id "*"; runtime.cmake stages it beside every game's own catalog.
 */
#include "mod_plugins.h"

#include <stdlib.h>

#define PKG_CD_SMOOTH "psx.enhancement.cd-audio-smoothing"

static void builtin_cd_audio_smoothing_activate(void) {
    char text[16] = "";
    long ms = 80;
    if (psx_mod_option_value(PKG_CD_SMOOTH, "cd-audio-smoothing", "prebuffer_ms",
                             text, sizeof text) && text[0]) {
        char* end = NULL;
        long v = strtol(text, &end, 10);
        if (end && *end == '\0' && v >= 0) ms = v;
    }
    (void)psx_mod_set_cd_audio_smoothing((uint32_t)ms);
}

PSX_MOD_CONSTRUCTOR(psx_register_builtin_audio_plugins) {
    (void)psx_mod_register_activation_plugin(
        "psx.cd-audio-smoothing", builtin_cd_audio_smoothing_activate);
}

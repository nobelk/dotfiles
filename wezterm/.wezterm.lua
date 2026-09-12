-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices.

-- For example, changing the initial geometry for new windows:
config.initial_cols = 80
config.initial_rows = 28

-- or, changing the font size and color scheme.
config.font_size = 14

-- color scheme
config.color_scheme = 'Catppuccin Macchiato'

-- performance
config.front_end = 'WebGpu'

-- font
config.font = wezterm.font('FiraMono Nerd Font Mono')

-- window cleanliness
config.window_decorations= 'RESIZE'
config.window_close_confirmation = 'NeverPrompt'

-- window opacity
config.window_background_opacity = .94
config.macos_window_background_blur = 20
config.window_padding = {
    left = 12,
    right = 12,
    top = 12, 
    bottom = 12,
}
config.hide_tab_bar_if_only_one_tab = true

-- visual bell
config.colors = {
    visual_bell = '#202020',
}
config.audible_bell = 'Disabled'

-- Key Bindings (Mac Style)
config.keys = {
  -- Split panes using Cmd + D and Cmd + Shift + D
  { key = 'D', mods = 'CMD', action = wezterm.action.SplitHorizontal { domain = 'CurrentPaneDomain' } },
  { key = 'D', mods = 'CMD|SHIFT', action = wezterm.action.SplitVertical { domain = 'CurrentPaneDomain' } },
  -- Close current pane
  { key = 'W', mods = 'CMD', action = wezterm.action.CloseCurrentPane { confirm = false } },
  -- Navigate panes with Cmd + hjkl
  { key = 'H', mods = 'CMD', action = wezterm.action.ActivatePaneDirection 'Left' },
  { key = 'L', mods = 'CMD', action = wezterm.action.ActivatePaneDirection 'Right' },
  { key = 'K', mods = 'CMD', action = wezterm.action.ActivatePaneDirection 'Up' },
  { key = 'J', mods = 'CMD', action = wezterm.action.ActivatePaneDirection 'Down' },
}


-- Finally, return the configuration to wezterm:
return config

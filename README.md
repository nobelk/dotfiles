# Dotfiles

Personal development environment configuration files for macOS. This repository contains settings and configurations for various text editors, shells, terminal multiplexers, and development tools optimized for Python development with support for multiple programming languages.

## Overview

This dotfiles repository provides a consistent development environment setup across:
- **Text Editors**: Sublime Text, Vim, Neovim, and Zed
- **Shell**: Zsh with custom prompt and productivity aliases
- **Terminal**: Tmux for session management
- **AI Tools**: Claude CLI with MCP server integration
- **Development Tools**: Python (Pyenv, Uv), Java (OpenJDK 11), and other language tooling

## Repository Structure

```
dotfiles/
├── claude/                 # Claude CLI configuration
│   ├── .claude/
│   │   └── settings.local.json
│   └── install-instructions.md
├── sublime/                # Sublime Text editor configuration
│   ├── Preferences.sublime-settings
│   ├── python.sublime-project
│   ├── python.sublime-workspace
│   ├── uv.sublime-build
│   └── uv.sublime-workspace
├── vim/                    # Vim and Neovim configuration
│   ├── .vimrc
│   └── init.vim
├── zsh/                    # Zsh shell configuration
│   ├── .zshrc
│   └── configure-zsh.sh
├── tmux/                   # Tmux terminal multiplexer configuration
│   └── .tmux.conf
└── zed/                    # Zed editor configuration
    └── settings.json
```

## Configuration Details

### Claude CLI (`claude/`)
- **Permissions**: Configured to allow bash commands with ripgrep (rg:*)
- **MCP Integration**: Setup instructions for AWS MCP server using uvx
- **AI-Assisted Development**: Integration with Claude AI for coding assistance

### Sublime Text (`sublime/`)
- **Theme**: GitHub Dark color scheme with Default Dark UI
- **Font**: Consolas, size 17
- **Python Focus**: Linting support for mypy, isort, and pytest
- **Build System**: Custom uv build configuration for Python projects
- **Features**: Word wrap, spell check, line highlighting, and custom word list for algorithm platforms (Leetcode, Algoexpert, Algomonster)

### Vim/Neovim (`vim/`)
- **Vim (.vimrc)**: Traditional Vim setup with Vundle plugin manager
  - Plugins: NerdTree, Lightline, indentation detection
  - Leader key: comma (,)
  - Language-specific configurations for Python, JavaScript, CoffeeScript, Twig, Markdown, YAML
  - Python abbreviations for common patterns (import, return, etc.)

- **Neovim (init.vim)**: Modern Vim fork with vim-plug
  - Plugins: fzf (fuzzy finder), vim-polyglot, airline, auto-pairs
  - Enhanced syntax highlighting and file navigation

### Zsh (`zsh/`)
- **Terminal**: iTerm2 with 256-color support (xterm-256color)
- **Prompt**: Custom green-colored prompt (#118)
- **Environment Setup**:
  - Pyenv for Python version management
  - Modular Mojo language support
  - Coursier and OpenJDK 11 for Java development
  - Antigravity package manager
- **Aliases**:
  - `ttop`: System process monitor
  - `lh`: List hidden files
- **Installation Script**: Automated setup for powerline, powerlevel9k, and syntax highlighting

### Tmux (`tmux/`)
- **Prefix Key**: Remapped from C-b to C-a
- **Pane Splitting**: Custom bindings (| for horizontal, - for vertical)
- **Navigation**: Alt-arrow for panes, Shift-arrow for windows
- **Behavior**: Windows numbered from 1, auto-renumber on close

### Zed (`zed/`)
- **AI Agent**: Claude Sonnet 4 integration
- **Theme**: Tokyo Night (dark) / One Light (light)
- **Font**: JetBrains Mono, 16pt
- **Keymap**: JetBrains IDE keybindings
- **Features**: Format on save, autosave after 30s, minimal UI (no scrollbars/cursor blink)

## Development Focus

### Primary Languages
- **Python**: Extensive tooling with Pyenv, Uv, mypy, pytest, isort
- **JavaScript/TypeScript**: Vim snippet support
- **Java**: OpenJDK 11 with Coursier dependency management
- **YAML, Markdown**: Proper indentation and syntax support

### Workflow Features
- **Algorithm Practice**: Custom word lists for competitive programming platforms
- **Linting & Testing**: Integration with mypy, pytest, and isort
- **Fuzzy Finding**: fzf integration in Neovim for quick file navigation
- **Session Management**: Tmux for persistent terminal sessions
- **AI Assistance**: Claude CLI for code generation and analysis

## Installation

To use these configurations:

1. Clone this repository:
   ```bash
   git clone https://github.com/nobelk/dotfiles.git ~/dotfiles
   ```

2. Symlink desired configuration files to your home directory:
   ```bash
   # Zsh
   ln -s ~/dotfiles/zsh/.zshrc ~/.zshrc

   # Vim
   ln -s ~/dotfiles/vim/.vimrc ~/.vimrc
   ln -s ~/dotfiles/vim/init.vim ~/.config/nvim/init.vim

   # Tmux
   ln -s ~/dotfiles/tmux/.tmux.conf ~/.tmux.conf
   ```

3. For Sublime Text, copy settings to your Packages/User directory:
   ```bash
   cp ~/dotfiles/sublime/Preferences.sublime-settings \
      ~/Library/Application\ Support/Sublime\ Text/Packages/User/
   ```

4. For Zed, copy settings to the Zed configuration directory:
   ```bash
   cp ~/dotfiles/zed/settings.json ~/.config/zed/
   ```

5. Run the Zsh configuration script for additional setup:
   ```bash
   bash ~/dotfiles/zsh/configure-zsh.sh
   ```

## Notes

- These configurations are optimized for macOS development
- Python development is heavily emphasized across all tools
- Color schemes and fonts may require additional installation
- Some plugins require manual installation on first use
- Claude CLI requires separate authentication setup

## License

Personal dotfiles for individual use.

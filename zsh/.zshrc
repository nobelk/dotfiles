# Ansi colors in ls and friends.
export CLICOLOR=1

# Prompt
PROMPT='%F{118}%C ~%f '

# Aliases
alias 'ttop=top -ocpu -R -F -s 2 -n30'
alias lh='ls -a | egrep "^\."'
alias img='chafa'
alias ls='eza --icons --grid --group-directories-first'

export PATH="$HOME/.local/bin:$PATH"

# Android SDK
export ANDROID_HOME="/opt/homebrew/share/android-commandlinetools"
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Dotnet tools
export PATH="$PATH:/Users/nobelk/.dotnet/tools"

# Go
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin


# Rust
export RUSTPATH=$HOME/.rustup/toolchains/stable-aarch64-apple-darwin
export PATH=$PATH:$RUSTPATH/bin

# sentry
fpath=("/Users/nobelk/.local/share/zsh/site-functions" $fpath)

# Pubcache
export PATH="$HOME/.pub-cache/bin:$PATH"

# Sublime Text (subl is symlinked into ~/.local/bin, already on PATH)
export EDITOR='subl -w'
export VISUAL="$EDITOR"
export PATH="/opt/homebrew/bin:$PATH"
export PATH="/opt/homebrew/sbin:$PATH"


# tmux shortcuts
alias ta='tmux attach-session -t'
alias tl='tmux list-sessions'
alias td='tmux detach'
alias ts='tmux new-session -s'
alias tk='tmux kill-session -t'
alias tka='tmux kill-server'
alias t='tmux attach || tmux new-session'

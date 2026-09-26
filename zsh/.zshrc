# Set CLICOLOR if you want Ansi Colors in iTerm2 
export CLICOLOR=1

# Set colors to match iTerm2 Terminal Colors
export TERM=xterm-256color

# Prompt
PROMPT='%F{118}%C ~%f '

export PATH="/opt/homebrew/bin:$PATH"

export PATH="$HOME/.local/bin:$PATH"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi


# Set GoPath
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Android Home
export ANDROID_HOME=$HOME/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools

# Chrome executable for Flutter web development (using Brave)
export CHROME_EXECUTABLE="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
export PATH="/opt/homebrew/opt/rustup/bin:$PATH"

# Default editor (Sublime Text); -w waits for the file to be closed
export EDITOR="subl -w"
export VISUAL="subl -w"
export GIT_EDITOR="subl -w"
eval "$(mise activate zsh)"
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
alias gp='git pull'
alias gs='git status'
alias 'ttop=top -ocpu -R -F -s 2 -n30'
alias lh='ls -a | egrep "^\."'
alias ls='eza --icons --grid --group-directories-first'
alias img='chafa'
alias wb='ssh -o ServerAliveInterval=30 nobelk@horizon'

# bun completions
[ -s "/Users/nobelk/.bun/_bun" ] && source "/Users/nobelk/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

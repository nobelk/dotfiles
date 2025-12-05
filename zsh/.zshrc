# Set CLICOLOR if you want Ansi Colors in iTerm2 
export CLICOLOR=1

# Set colors to match iTerm2 Terminal Colors
export TERM=xterm-256color

# Prompt
PROMPT='%F{118}%C ~%f '

# Aliases
alias 'ttop=top -ocpu -R -F -s 2 -n30'
alias lh='ls -a | egrep "^\."'

# Export
export MODULAR_HOME="/Users/nobelkhandaker/.modular"
export PATH="/Users/nobelkhandaker/.modular/pkg/packages.modular.com_mojo/bin:$PATH"
export PATH="~/Library/Application Support/Coursier/bin:$PATH"

# Pyenv configurations
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
export PATH="/opt/homebrew/opt/openjdk@11/bin:$PATH"
export MODULAR_HOME="/Users/nobelkhandaker/.modular"
export PATH="/Users/nobelkhandaker/.modular/pkg/packages.modular.com_mojo/bin:$PATH"

# Added by Antigravity
export PATH="/Users/nobelkhandaker/.antigravity/antigravity/bin:$PATH"

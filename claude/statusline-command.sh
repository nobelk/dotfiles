#!/bin/sh
input=$(cat)
dir=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
basename_dir=$(basename "$dir")
model=$(echo "$input" | jq -r '.model.display_name // ""')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# Green color (ansi 118) for directory, matching original zsh PROMPT color
status=$(printf "\033[38;5;118m%s\033[0m" "$basename_dir")

# Append git branch and dirty/clean state if inside a git repo
git_branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$git_branch" ]; then
  git_dirty=$(git -C "$dir" status --porcelain 2>/dev/null)
  if [ -n "$git_dirty" ]; then
    git_state="*"
  else
    git_state=""
  fi
  status="$status  git:${git_branch}${git_state}"
fi

# Append model name if available
if [ -n "$model" ]; then
  status="$status  $model"
fi

# Append context usage if available
if [ -n "$used" ]; then
  used_int=$(printf "%.0f" "$used")
  status="$status  ctx:${used_int}%"
fi

# Append 5-hour (daily) and 7-day (weekly) rate limit usage if available
rate_info=""
if [ -n "$five_pct" ]; then
  five_int=$(printf "%.0f" "$five_pct")
  rate_info="daily:${five_int}%"
fi
if [ -n "$week_pct" ]; then
  week_int=$(printf "%.0f" "$week_pct")
  if [ -n "$rate_info" ]; then
    rate_info="${rate_info} weekly:${week_int}%"
  else
    rate_info="weekly:${week_int}%"
  fi
fi
if [ -n "$rate_info" ]; then
  status="$status  $rate_info"
fi

printf "%s" "$status"

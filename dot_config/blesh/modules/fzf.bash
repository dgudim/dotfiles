# This file provides the following:
# - Fuzzy-find a file/dir and print to stdout (ctrl-t)
# - Fuzzy-find a directory and cd into it (alt-c)
# - Fuzzy-fing a file and open in (fop)
# - Ripgrep with syntax highlighting and fzf selection (rga-fzf)
# - Fuzzy-grep (rg-fzfc)
# - Ripgrep with syntax highlighting (rgc and rgac)

export __LS_COLORS=$(vivid generate gruvbox-dark)
export __FZF_PREVIEW_WINDOW="right,50%,wrap,border-sharp"

fd() {
	LS_COLORS="$__LS_COLORS" /usr/bin/fd -L --max-depth 10 "$@";
}

# Override default fzf completion, add bat preview (ctrl-t)
export FZF_CTRL_T_OPTS="--preview \"fzf-handle-preview.sh {}\" --preview-window=\"$__FZF_PREVIEW_WINDOW\" --prompt 'Search all> '"
export FZF_DEFAULT_OPTS='--color=bg+:#32302f,bg:#282828,spinner:#fb4934,hl:#928374,fg:#ebdbb2,header:#928374,info:#8ec07c,pointer:#fb4934,marker:#fb4934,fg+:#ebdbb2,prompt:#fb4934,hl+:#fb4934 --ansi --no-mouse --bind "alt-up:preview-half-page-up,alt-down:preview-half-page-down"'

export FZF_CTRL_T_COMMAND="fd --color always -t f -t d -t l"

# Override default fzf completion, add colors
export FZF_ALT_C_COMMAND="fd --min-depth 1 --color always -t d -t l"
export FZF_ALT_C_OPTS="--prompt 'Cd into> '"

# __fzf_select__ ()
# {
#     local cmd opts;
#     cmd="${FZF_CTRL_T_COMMAND:-"command find -L . -mindepth 1 \\( -path '*/.*' -o -fstype 'sysfs' -o -fstype 'devfs' -o -fstype 'devtmpfs' -o -fstype 'proc' \\) -prune     -o -type f -print     -o -type d -print     -o -type l -print 2> /dev/null | command cut -b3-"}";
#     opts="--height ${FZF_TMUX_HEIGHT:-40%} --bind=ctrl-z:ignore --reverse --scheme=path ${FZF_DEFAULT_OPTS-} ${FZF_CTRL_T_OPTS-} -m";
#     eval "$cmd" | FZF_DEFAULT_OPTS="$opts" $(__fzfcmd) "$@" | while read -r item; do
#         printf '%q ' "$item";
#     done
# }

# __fzf_cd__ ()
# {
#     local cmd opts dir;
#     cmd="${FZF_ALT_C_COMMAND:-"command find -L . -mindepth 1 \\( -path '*/.*' -o -fstype 'sysfs' -o -fstype 'devfs' -o -fstype 'devtmpfs' -o -fstype 'proc' \\) -prune     -o -type d -print 2> /dev/null | command cut -b3-"}";
#     opts="--height ${FZF_TMUX_HEIGHT:-40%} --bind=ctrl-z:ignore --reverse --scheme=path ${FZF_DEFAULT_OPTS-} ${FZF_ALT_C_OPTS-} +m";
#     dir=$(set +o pipefail; eval "$cmd" | FZF_DEFAULT_OPTS="$opts" $(__fzfcmd)) && printf 'builtin cd -- %q' "$dir"
# }

__rgX-fzf() {
	local file RG_PREFIX;
	RG_PREFIX="exa --color=always \$($1 --files-with-matches --line-buffered \"\${@:3}\""
	fzf --sort \
		--preview="[[ ! -z {} ]] && $1 --line-number --line-buffered --context 5 --json {q} {} | delta --pager=0" \
		--disabled -q "$2" \
		--bind "start:reload:$RG_PREFIX {q})" \
		--bind "change:reload:sleep 0.1; $RG_PREFIX {q}) || true" \
		--preview-window="$__FZF_PREVIEW_WINDOW" \
		--bind 'enter:become(xdg-open {})'
}

# Search everything by content, including pdfs and archives, display preview with fzf
rga-fzf() {
    __rgX-fzf rga "$@"
}
# Search text files by content, display preview with fzf
rg-fzf() {
    __rgX-fzf rg "$@"
}
# Fuzzy-grep (kinda) (initial grep via ripgrep, then fzf)
rg-fzfc() {
    local file;
	rg --line-number --line-buffered --color=always --no-heading "${@:-}" 2> /dev/null |
	fzf --ansi --sort \
		--color "hl:-1:underline,hl+:-1:underline:reverse" \
		--delimiter : \
		--preview '[[ ! -z {} ]] && bat --color=always {1} --highlight-line {2} --pager=never --style full' \
		--preview-window "$__FZF_PREVIEW_WINDOW,+{2}+3/3,~3" \
		--bind 'enter:become(kate {1} --line {2})'
}
# Search only text files
rgc() {
	rg --json "$@" | delta --pager=0
}
# Search everything, including pdfs and archives
rgac() {
	rga --json "$@" | delta --pager=0
}
fzf-preview() {
	fzf -q "$1" --sort --preview "[[ ! -z {} ]] && fzf-handle-preview.sh {}" --preview-window="$__FZF_PREVIEW_WINDOW" --prompt 'Search> ' "${@:2}"
}
# Fuzzy-open a file
fop() {
    local file;
	file="$(fd --color always -t f "${@:2}" | fzf-preview "$1")" && xdg-open "$file"
}


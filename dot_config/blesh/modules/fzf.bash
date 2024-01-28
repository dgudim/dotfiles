# This file provides the following:
# - Fuzzy-find a file/dir and print to stdout (ctrl-t)
# - Fuzzy-find a directory and cd into it (alt-c)
# - Fuzzy-fing a file and open in (fop)
# - Ripgrep with syntax highlighting and fzf selection (rga-fzf)
# - Fuzzy-grep (rg-fzfc)
# - Ripgrep with syntax highlighting (rgc and rgac)

# Override default fzf completion, add bat preview (ctrl-t)
export FZF_CTRL_T_OPTS="--preview \"bat --color=always --line-range=:500 {}\" --preview-window=\"50%:wrap\" --prompt 'All> '"
export FZF_DEFAULT_OPTS='--color=bg+:#32302f,bg:#282828,spinner:#fb4934,hl:#928374,fg:#ebdbb2,header:#928374,info:#8ec07c,pointer:#fb4934,marker:#fb4934,fg+:#ebdbb2,prompt:#fb4934,hl+:#fb4934 --ansi'
export FZF_CTRL_T_COMMAND="export LS_COLORS=\"\$(vivid generate gruvbox-dark)\"; fd -L --min-depth 1 --color always --max-results 300 -t f -t d -t l -t x -t e --unrestricted; unset LS_COLORS"

# Override default fzf completion, add colors
export FZF_ALT_C_COMMAND="export LS_COLORS=\"\$(vivid generate gruvbox-dark)\"; fd -L --min-depth 1 --color always --max-results 300 -t d -t l --unrestricted; unset LS_COLORS"
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

# Search everything by content, including pdfs and archives, display preview with fzf
rga-fzf() {
    local file RG_PREFIX;
	RG_PREFIX="rga --files-with-matches --ignore-case"
	file="$(fzf --sort \
				--preview="[[ ! -z {} ]] && rga --context 5 --json {q} {} | delta --pager=0" \
				--phony -q "$1" \
				--bind "start:reload:$RG_PREFIX {q}" \
		        --bind "change:reload:sleep 0.1; $RG_PREFIX {q} || true" \
				--preview-window="70%:wrap")" && xdg-open "$file"
}
# Fuzzy-grep (kinda) (initial grep via ripgrep, then fzf)
rg-fzfc() {
    local file;
	rg --line-buffered --color=always --line-number --no-heading --ignore-case "${*:-}" 2> /dev/null |
	file="$(fzf --ansi --sort \
		--color "hl:-1:underline,hl+:-1:underline:reverse" \
		--delimiter : \
		--preview '[[ ! -z {} ]] && bat --color=always {1} --highlight-line {2}' \
		--preview-window="70%:wrap")" && xdg-open "$file"
}
# Search only text files
rgc() {
	rg --json "$@" | delta --pager=0
}
# Search everything, including pdfs and archives
rgac() {
	rga --json "$@" | delta --pager=0
}
# Fuzzy-open a file
fop() {
    local cmd file;
	cmd="export LS_COLORS=\"\$(vivid generate gruvbox-dark)\"; fd -L --color always --max-results 300 -t f --unrestricted \$@; unset LS_COLORS";
	file="$(eval "$cmd" | fzf --sort --preview "bat --color=always --line-range=:500 {}" --preview-window="50%:wrap" --prompt 'Search file> ')" && xdg-open "$file"
}

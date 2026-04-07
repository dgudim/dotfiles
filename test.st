if [[ "$(whoami)" != "root" ]]; then
    # Add user stuff to PATH
    # Escape home variable for proper sed substitution
    HOME_ESC=$(echo "$HOME" | sed 's/\//\\\//g')
    XDG_DATA_HOME_ESC=$(echo "$XDG_DATA_HOME" | sed 's/\//\\\//g')
    CLEAN_PATH=$(echo "$PATH" |
        sed "s/$XDG_DATA_HOME_ESC\/cargo\/bin://g" |
        sed "s/$HOME_ESC\/.local\/bin://g" |
        sed "s/$XDG_DATA_HOME_ESC\/go\/bin://g" |
        sed "s/$HOME_ESC\/Documents\/usefull_files\/scripts://g" |
        sed "s/:$XDG_DATA_HOME_ESC\/dotnet\/tools//g")
    echo "~/.local/bin:$XDG_DATA_HOME/cargo/bin:$XDG_DATA_HOME/go/bin:$HOME/Documents/usefull_files/scripts:$CLEAN_PATH:$XDG_DATA_HOME/dotnet/tools/"

    # Rootless docker
    export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock

    export GPG_TTY="$(tty)"
    export SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
else
    unset GPG_TTY
    unset SSH_AUTH_SOCK
fi

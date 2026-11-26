while true; do

    cat <<EOF
digraph {
  A -> B;
}

EOF
    printf '\0'
    sleep 1

    cat <<EOF
digraph {
  A -> B;
  B -> C;
}

EOF
    printf '\0'
    sleep 1

    cat <<EOF
digraph {
  A -> B;
  B -> C;
  B -> D;
}

EOF
    printf '\0'
    sleep 1

    cat <<EOF
digraph {
  A -> B;
  B -> C;
  B -> D;
  C -> E;
}

EOF
    printf '\0'
    sleep 1

    cat <<EOF
digraph {
  A -> B;
  B -> C;
  B -> D;
  C -> E;
  D -> E;
}

EOF
    printf '\0'
    sleep 1
done

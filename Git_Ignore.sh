#!/bin/sh

# This script simply adds the usual kind of files
# that I do not want to be taken into account by
# git

cat > .gitignore <<-__EOF__
.un*
*.log
*.dvi
*.aux
*.out
*.blg
*.tns
*.toc
*.nav
*.snm
*.bak
*~
*.tmp
*.tui
*.tuo
*.mpo
*mpgraph*
*bbl
*.pyg
*.vrb
*.llt
.gitignore
__EOF__


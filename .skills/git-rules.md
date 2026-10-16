# Git Workflow (NON-NEGOTIABLE)
- NEVER execute `git commit`, `git add`, `git stash`, or any history-altering command.
- The human developer owns the commit history.
- After completing a task: 1) Make changes, 2) Run `make lint` & `make test`, 3) Summarize changes, 4) STOP and wait for approval.

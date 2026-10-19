# Git Workflow (NON-NEGOTIABLE)

## Hard rules
- NEVER execute `git commit`, `git add`, `git stash`, `git reset --hard`,
  `git checkout --`, `git revert`, `git rebase`, branch/tag creation, or any
  other command that writes to the git index, working tree, or history.
- The human developer owns and reviews every commit.

## What to do instead

1. Make the code/documentation/config changes in the working tree.
2. Run the verification suite: `make lint` and `make test` (plus
   `make migrations-check` / `make check` when models or settings changed).
3. Report a summary: files modified, files added, tests added or changed, and
   the verification results.
4. **Notify via Telegram**: execute a brief notification with `telegram-send`
   containing a 1-2 sentence summary of the completed work.
   - **CRITICAL**: always append the fallback so the workflow never fails when
     the CLI is momentarily unavailable or unconfigured.
   - Exact command pattern:

     ```bash
     telegram-send "✅ Task Completed: [Brief summary of changes, e.g., 'Added restore_db.sh and updated CI pipeline']" || echo "Telegram notification skipped (tool not configured)"
     ```

   - Keep the message concise: respect Telegram's length limits and the
     developer's attention.
5. **Stop and wait for explicit developer approval.** Do not treat the task as
   finished, and do not start follow-up work, until it is given.

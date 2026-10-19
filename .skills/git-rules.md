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
   - **CRITICAL**: always append the fallback. The CLI exits non-zero on every
     Telegram API error, and the workflow must never break because of it.
   - Exact command pattern:

     ```bash
     telegram-send "✅ Task Completed: [Brief summary]" 2>/dev/null || echo "Telegram notification skipped (tool not configured)"
     ```

   - Keep the message to one line and under ~300 characters: respect Telegram's
     limits and the developer's attention.
   - The CLI sends **Markdown** by default and answers `HTTP 400` when the text
     contains unbalanced Markdown markers. Write plain prose: no `_`, `*`,
     backticks, or `[` in the message. A single identifier such as `account_id`
     is enough to make the send fail. If an identifier is unavoidable, escape
     each underscore (`account\_id`).
   - Do **not** pass `-m plain`: on this installation that mode sends an invalid
     `parse_mode` and always fails with `HTTP 400`, whatever the message.
     `-m html` works, but then `<`, `>`, and `&` must be escaped.
   - Keep `2>/dev/null`: a failure otherwise prints a traceback that includes
     the bot token in the request URL. The fallback `echo` is the only signal
     needed.
5. **Stop and wait for explicit developer approval.** Do not treat the task as
   finished, and do not start follow-up work, until it is given.

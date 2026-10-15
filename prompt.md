# Homework 5 — Draft Prompts

Proposed prompts for review, organized like Homework 3. These are drafts, not a record of prompts already typed or work already completed. Add actual prompts and any needed follow-ups to `AI_prompts.md` as each problem is worked on.

## Problem 1: Vibe coder prompts

> Set up AI_prompts.md like Homework 3, with one section per problem. Record the prompts I use as we work. If I need a follow-up, include it and a short explanation of what the first result was missing.

## Problem 2: Study the Campus Customs database

> Look through every table and field in data/campus_customs.db and explain how the three open tickets connect to the other tables. Make a working copy called campus_customs_new.db and keep the original unchanged. Start output/harness.md with the fields in each table and a short explanation of why the agents need it.

## Problem 3: Build the MCP server

> Create a FastMCP server in mcp_server/server.py using the working database. Start with three useful tools for tickets 101, 102, and 103. Use only database facts. For now, write the server without connecting or running it. In the harness, explain which tables each tool reads, which ticket it helps with, and why. Add mcp_server/README.md explaining the server, database, and tools.

## Problem 4: Add the MCP server to vibe coder and test each tool

> Connect this project's MCP server to the vibe coder and save the local connection configuration. Test all three tools through the connection. Save the actual prompt, tool name, and returned output for each test in output/mcp_smoke.json. Check that the results agree with the working database.

## Problem 5: Build the agent team and grow the MCP tools

> Build the Boss, Inventory, Accounting, Facilities, and Customer Service agents with PydanticAI. Put one detailed prompt per agent in backend/prompts/ and the data models in backend/models.py. Any agent should be able to delegate to any other agent. Use only gpt-6-luna through Portkey with PORTKEY_API_KEY.
>
> Add the MCP tools needed to handle the tickets. All shop data access should go through MCP. Use the shop date and vendor lead times from the database. Vendors with unpaid invoices cannot ship. Payments need human approval, cash cannot go negative, and customer messages stay as drafts. Append real agent steps to output/audit_trail.json. Update the harness and MCP README with the agents, tools, tables, safety rules, and limits on loops, delegation, and token use.

## Problem 6: Plan the three tickets

> Before running the team, create output/desk_tickets.html with a tab for each ticket and separate Cash and Reflection tabs. Fill only the Expected section for each ticket. Explain who Boss should contact first, why, the delegations that should follow, and the MCP tools needed. Keep the plan specific to each ticket. Leave Actual, Cash, and Reflection for later.

## Problem 7: Backend routes

> Build the FastAPI backend in backend/main.py. Add routes to list ticket statuses, start a ticket run, return recent agent messages and tool events, approve prepared payments or purchases, show checking cash, and reset the working database. Agents should prepare requests; the human approval route should trigger the cash change through MCP. Document each route in the harness and make the backend runnable on port 8000.

## Problem 8: Agent dashboard

> Build a polished React, Vite, and TypeScript dashboard in frontend/. Show all three tickets, let me start one, and display what each agent says and does during the run. Show ticket status, a short summary of each agent's contribution, payment or purchase approval requests, and the checking balance after approvals. Connect it to the backend on port 8000 and configure CORS for Vite. Explain the layout and visual choices in output/design.md.

## Problem 9: Resolve the tickets

> Reset the working database and record the starting checking balance. Run tickets 101, 102, and 103 through the dashboard, pausing for me to review and approve payment or purchase requests. Use the real run events to fill each ticket's Actual section while keeping Expected unchanged.
>
> On the Cash tab, show the starting balance, each ticket's payments or purchases and amounts, and the ending balance. Reconcile it to the database. Save final statuses, outcomes, agent contributions, and approvals in output/resolved_tickets.json. Capture the React board for each resolved ticket and include those screenshots in output/resolved_board.html. Keep appending the audit trail and finish the harness.

## Problem 10: Reflection

> Draft the Reflection tab using the actual ticket runs and cash results. Evaluate each ticket, compare Actual with Expected, and explain what would have been simpler with one agent and tools. Give three new Campus Customs problems this team could solve and three it could not solve yet, including the extra agents or tools needed. Keep it specific to this app and show me the draft so I can add my own assessment.

## Problem 11: Submit to GitHub

> Prepare the Homework 5 repository with the required code, both databases, outputs, dependencies, example environment file, and local MCP configuration. Keep secrets out of the files and Git history. Write a README explaining setup, resetting the working database, and starting MCP, FastAPI, and React. Check the required file layout and let me preview the finished work before publishing. When I ask to publish, save the public repository URL in output/github_url.txt for my Canvas submission.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resell-Agent is a greenfield AI agent system for reselling items. The intended workflow:

1. **Marketing agent** — generates item descriptions and suggests prices based on market data
2. **Inventory agent** — organizes items into a spreadsheet or structured inventory
3. **Negotiation agent** — negotiates sale prices within owner-defined parameters
4. **Human approval gate** — owner reviews and approves the final price before any deal is accepted

The `.gitignore` is a Node.js template, indicating the planned stack is JavaScript/TypeScript with npm/yarn/pnpm.

## Current State

The repository contains only a README and `.gitignore`. No source code, dependencies, tests, or configuration files exist yet. All agent logic, data models, and tooling are yet to be built.

## Architecture Intent

When implementing, keep these design constraints in mind from the README:

- **Multi-agent**: separate concerns across specialized agents (pricing/description, inventory, negotiation) rather than one monolithic agent
- **Human-in-the-loop**: the negotiation agent must never finalize a price without explicit owner approval — this is a hard requirement, not an optional check
- **Parameter-driven negotiation**: the owner defines acceptable price ranges/floors before any negotiation begins; the agent operates within those bounds only
- **Structured output**: inventory must be exportable to a spreadsheet format (CSV or Google Sheets integration likely)

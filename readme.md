# Ranch Sale Dashboard

A working system built to manage a real ranch sale transaction in Valencia County, New Mexico.

A decision-focused dashboard built to govern a real-world ranch sale transaction.

This system tracks deal stages, document verification, and operational blockers so that the next action and responsible party are always visible.

Instead of simply storing information, the dashboard enforces workflow rules to prevent mistakes and delays.


## The Problem 

Land sales involve multiple parties and documents: 

- buyer 

- realtor 

- title company 
 
- surveyor 

- county records 

- environmental records 


In practice, deals often stall because: 

- documents are missing 

- responsibilities are unclear 

- status is scattered across emails and notes  

The goal of this system is to make the current state of the deal instantly clear. 

 

## Core Concept 

The dashboard answers four questions at any moment: 

What stage is the deal in? 

What is blocking progress? 

What needs to happen next? 

Who is responsible? 

These answers are computed automatically from the system state. 

 

## Key Features 

Stage Governance 

The deal moves through defined stages: 



locate_buyer → negotiate → appraisal → due_diligence → disclosure → contract_signed → title_review → closing → completed 

 

 

The system prevents invalid transitions. 

  

For example: 

- closing cannot occur without verified documents 

  

--- 

  

### Document Verification 

  

Each document moves through statuses: 

 

missing → requested → received → verified 

 

Documents required for later stages must be verified before progress is allowed. 

  

--- 

  

### Deal Health Signal 

  

The system automatically evaluates deal status. 

  

| Health | Meaning | 

|------|------| 

| OK | workflow progressing normally | 

| BLOCKED | required documents missing | 

| DELAYED | stage taking too long | 

  

--- 

  

### Automatic Next Action 

  

Instead of just displaying data, the system computes: 

Next Action 

Responsible Party 

 

 

--- 

  

### Activity Log 

  

Every meaningful change is recorded: 

  

- document updates 

- stage changes 

- deal field updates 

  

This creates a full operational history of the transaction. 

  

--- 

  

# Architecture 

```
Streamlit UI
   ↓
rules.py (workflow governance)
   ↓
db.py (state + activity logging)
   ↓
SQLite database
```


Separation of responsibilities: 

| File | Purpose |
|-----|-----|
| app.py | Dashboard interface |
| rules.py | Workflow governance rules |
| db.py | Persistence + activity log |
| seed.py | Demo data initialization |

 

# Technology 

Python 

Streamlit 

SQLite 

The stack was intentionally kept lightweight to emphasize system design and governance logic, not framework complexity. 

 

# Running the Dashboard 

Install dependencies 

```bash
pip install streamlit
```

```bash
python seed.py
```

```bash
streamlit run app.py
``` 

### Start the dashboard 
 

The dashboard will open at: 

 

http://localhost:8501 


# Design Decisions 

Decision-First Interface 

The UI emphasizes next action and responsibility, not raw data. 

 

Rules Separate from UI 

Workflow rules live in rules.py. 

This allows governance logic to change without modifying the interface. 

 

State Separate from Logic 

Database operations live in db.py. 

This prevents workflow rules from being mixed with storage logic. 

 

# Future Improvements 

Possible extensions include: 

multi-deal support 

document uploads 

notification reminders 

hosted deployment 

role-based access control 

 

# Why This Artifact Exists 

This project was built to demonstrate systems thinking through a real operational workflow.

The focus is not just code, but:
- operational governance
- workflow enforcement
- decision clarity
 
# Author 

Que Armendariz 

Systems Design · AI Governance · Workflow Automation 

LinkedIn 

https://www.linkedin.com/in/que-armendariz-5606243ab/ 

 
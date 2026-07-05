# Dashboard Environment Inspection

Inspection was performed before selecting the final dashboard delivery technology.

## Checked
- `PBIDesktop` command lookup
- `pbi-tools` command lookup
- `TabularEditor` and `TabularEditor3` command lookup
- Microsoft Store/Appx package lookup for Power BI
- Windows uninstall registry entries for Power BI, pbi-tools, and Tabular Editor
- Common install folders under Program Files and user-local app locations

## Result
Power BI Desktop, PBIP command-line tooling, pbi-tools, and Tabular Editor were not found as accessible local tooling in this environment.

## Delivery Decision
Because native `.pbix` or `.pbip` creation was not technically available, the project delivers a finished standalone HTML analytics dashboard generated from the validated project data. The dashboard is recruiter-ready, requires no external server, and does not require the user to manually construct visuals.

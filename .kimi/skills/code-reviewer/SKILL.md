---
name: code-reviewer
description: |
  Use this skill automatically after completing a major coding step or feature implementation. AI should run this skill without waiting for user request.
---

### Purpose of use
The purpose of using this skill is to review the completed project steps according to the original plan and ensure compliance with code quality standards.

### Trigger Rule
- **AI automatically runs** this skill after completing any major feature, component, or significant code block
- **User-requested review**: Only when the developer explicitly asks for a system-level comprehensive review, use the global `requesting-code-review` skill instead

### What should you do
When reviewing completed work, you will:

1. **Plan Alignment Analysis**:
   - Compare the implementation against the original plan or step description
   - Identify any deviations from the planned approach, architecture, or requirements
   - Assess whether deviations are justified improvements or problematic departures
   - Verify that all planned functionality has been implemented
2. **Code Quality Assessment**:
   - Review code for adherence to established patterns and conventions
   - Check for proper error handling, type safety, and defensive programming
   - Evaluate code organization, naming conventions, and maintainability
   - Look for potential security vulnerabilities or performance issues
3. **Architecture and Design Review**:
   - Ensure the implementation follows SOLID principles and established architectural patterns
   - Check for proper separation of concerns and loose coupling
   - Verify that the code integrates well with existing systems
   - Assess scalability and extensibility considerations
4. **Documentation and Standards**:
   - Verify that code includes appropriate comments and documentation
   - Check that file headers, function documentation, and inline comments are present and accurate
   - Ensure adherence to project-specific coding standards and conventions
5. **Issue Identification and Recommendations**:
   - Clearly categorize issues as: Critical (must fix), Important (should fix), or Suggestions (nice to have)
   - For each issue, provide specific examples and actionable recommendations
   - When you identify plan deviations, explain whether they're problematic or beneficial
   - Suggest specific improvements with code examples when helpful
6. **Communication Protocol**:
   - If you find significant deviations from the plan, present them, ask for confirm
   - If you identify issues with the original plan itself, recommend plan updates
   - For implementation problems, provide clear guidance on fixes needed
   - Always acknowledge what was done well before highlighting issues

Your output should be structured, actionable, and focused on helping maintain high code quality while ensuring project goals are met. Be thorough but concise, and always provide constructive feedback that helps improve both the current implementation and future development practices.

# AI Prompting Best Practices

This guide will help you write effective prompts when working with AI coding assistants. Good prompting is a crucial skill for successful AI collaboration.

## Core Principles

### 1. Be Specific and Clear
Vague prompts lead to vague results. Always provide specific details about what you want.

**❌ Bad:** "Write a function"
**✅ Good:** "Write a Python function that validates email addresses using regex, returns True for valid emails and False for invalid ones, and includes proper error handling for malformed input"

### 2. Provide Context
Help the AI understand your project structure and requirements.

**❌ Bad:** "Add error handling to this code"
**✅ Good:** "Add error handling to this TaskManager.get_task() method. It should raise ValueError with a descriptive message when a task ID doesn't exist. Here's the current code: [code snippet]"

### 3. Specify Format and Style
Tell the AI how you want the output formatted and what style to follow.

**❌ Bad:** "Generate tests for this function"
**✅ Good:** "Generate pytest unit tests for this function using the AAA pattern (Arrange, Act, Assert). Include edge cases and follow the naming convention test_[function_name]_[scenario]. Use descriptive assertions with clear error messages."

## Effective Prompting Patterns

### Pattern 1: The Requirements Prompt
Structure: Context + Requirements + Constraints + Examples

```
I'm building a task management application in Python. I need a function that:

Requirements:
- Filters tasks by priority level (high, medium, low)
- Returns a list of matching tasks
- Supports multiple priority levels as input
- Preserves original task order within each priority

Constraints:
- Must use type hints
- Include docstring with examples
- Handle edge cases (empty list, invalid priorities)
- Follow Python naming conventions

Example usage:
filtered_tasks = filter_by_priority(tasks, ['high', 'medium'])
```

### Pattern 2: The Review and Improve Prompt
Structure: Code + Specific review areas + Improvement goals

```
Please review this code for:
1. Code quality and readability
2. Potential security vulnerabilities
3. Performance optimizations
4. Error handling improvements

[Insert code here]

Focus on making the code more maintainable and robust. Suggest specific improvements with explanations.
```

### Pattern 3: The Debugging Prompt
Structure: Problem description + Error message + Code + Expected behavior

```
I'm getting this error: [error message]

Problem: The function should calculate the total completion time for tasks but it's failing when tasks have None values for completion_time.

Current code:
[code snippet]

Expected behavior: Should skip tasks with None completion_time and calculate total for completed tasks only.
```

### Pattern 4: The Refactoring Prompt
Structure: Current code + Refactoring goal + Specific patterns/principles

```
Please refactor this code to implement the Strategy pattern:

Current code:
[code snippet]

Goal: Make the sorting algorithm configurable so I can easily switch between different sorting strategies (by priority, by date, by completion status).

Requirements:
- Create abstract base class for strategies
- Implement concrete strategies
- Update the main class to use strategies
- Maintain backward compatibility
```

## Domain-Specific Prompts

### For Code Generation
```
Create a [language] [component type] that:
- [Specific functionality 1]
- [Specific functionality 2]
- [Specific functionality 3]

Technical requirements:
- [Framework/library constraints]
- [Performance requirements]
- [Security considerations]

Code style:
- [Naming conventions]
- [Documentation style]
- [Error handling approach]

Example usage:
[Show how the code should be used]
```

### For Testing
```
Generate comprehensive tests for this [function/class]:

[Insert code]

Test coverage should include:
- Happy path scenarios
- Edge cases: [list specific edge cases]
- Error conditions: [list error scenarios]
- Integration with: [related components]

Use [testing framework] with:
- [Assertion style]
- [Mock/fixture requirements]
- [Test organization approach]
```

### For Documentation
```
Create documentation for this [function/class/module]:

[Insert code]

Documentation should include:
- Clear description of purpose
- Parameter descriptions with types
- Return value description
- Usage examples
- Common pitfalls or gotchas
- Related functions/classes

Format: [Specify format: docstring, markdown, etc.]
```

## Advanced Prompting Techniques

### 1. Iterative Refinement
Start with a basic prompt, then refine based on the response:

```
Initial: "Create a data validator class"
Refined: "Create a data validator class that validates task data with custom rules for each field"
Further refined: "Create a data validator class that validates task data using a rule-based system where each field can have multiple validation rules (required, type, length, format) and returns detailed error messages for failed validations"
```

### 2. Role-Based Prompting
Ask the AI to take on a specific role:

```
Act as a senior Python developer reviewing this code for a production system. Focus on:
- Security vulnerabilities
- Performance bottlenecks
- Maintainability issues
- Best practices violations

[Insert code]
```

### 3. Constraint-Driven Prompting
Provide specific constraints to guide the solution:

```
Implement a caching mechanism with these constraints:
- Memory usage must not exceed 100MB
- Cache hit ratio should be >80% for typical usage
- Thread-safe for concurrent access
- Configurable eviction policies
- No external dependencies beyond standard library
```

### 4. Example-Driven Prompting
Provide examples of input/output or usage patterns:

```
Create a function that transforms task data like this:

Input: {"id": 1, "title": "Buy groceries", "priority": "high", "completed": false}
Output: {"taskId": 1, "name": "Buy groceries", "urgency": "HIGH", "isDone": false}

Rules:
- id → taskId
- title → name
- priority → urgency (uppercase)
- completed → isDone
```

## Common Pitfalls to Avoid

### 1. Overly Complex Prompts
Don't try to solve everything in one prompt. Break complex requests into smaller, focused prompts.

### 2. Insufficient Context
Provide enough information for the AI to understand your specific use case and requirements.

### 3. Ignoring AI Limitations
Remember that AI may not always produce perfect code. Always review and test the output.

### 4. Not Iterating
Don't accept the first response if it's not quite right. Ask follow-up questions to refine the solution.

## Prompt Templates

### Quick Reference Templates

#### Bug Fix Template
```
I have a bug in this code:
[code snippet]

Error: [error message]
Expected behavior: [what should happen]
Current behavior: [what actually happens]

Please identify the issue and provide a fix with explanation.
```

#### Code Review Template
```
Please review this code for:
- [specific aspect 1]
- [specific aspect 2]
- [specific aspect 3]

[code snippet]

Provide specific suggestions for improvement.
```

#### Implementation Template
```
Implement a [component] that:
- [requirement 1]
- [requirement 2]
- [requirement 3]

Constraints:
- [constraint 1]
- [constraint 2]

Style: [coding style preferences]
```

## Working with AI Responses

### 1. Review and Understand
Always read through AI-generated code carefully before using it. Make sure you understand how it works.

### 2. Test Thoroughly
Run the code and test it with various inputs to ensure it works as expected.

### 3. Adapt to Your Context
Modify the AI's suggestions to fit your specific project structure and requirements.

### 4. Ask for Explanations
If something isn't clear, ask the AI to explain its reasoning or approach.

### 5. Iterate and Improve
Use follow-up prompts to refine the solution based on your needs.

## Practice Exercises

1. **Write a prompt** to generate a configuration management system
2. **Create a debugging prompt** for a hypothetical error in your task manager
3. **Develop a code review prompt** for a specific function in your project
4. **Design a refactoring prompt** to improve code organization

## Remember

- **Quality over quantity**: A well-crafted prompt is more valuable than multiple vague ones
- **Specificity matters**: The more specific your prompt, the better the AI's response
- **Context is key**: Always provide sufficient background information
- **Iterate and improve**: Don't expect perfect results on the first try
- **Review everything**: AI is a tool to assist you, not replace your judgment

Good prompting is a skill that improves with practice. Keep experimenting and refining your approach!
I understand you're looking to build a DB-first multi-agent framework that integrates with a fork of fast-agent. This is an interesting architectural challenge, especially given your RDBMS background and the desire for high cohesion despite tighter coupling.

Based on the fast-agent README you shared, I can see it uses a declarative approach with minimal boilerplate, which actually makes it a good candidate for integration with a database-centric architecture.

## High-Level Architecture Recommendation

I'd recommend a layered architecture where your database serves as the central source of truth, with fast-agent handling the agent execution layer. Here's how I envision it:

1. **Database Layer** - The foundation and source of truth
2. **Middleware/Persistence Layer** - Translates between DB models and fast-agent objects
3. **Agent Execution Layer** - Your forked fast-agent
4. **API Layer** - External interfaces to your system

### Key Components:

#### 1. Database Schema Design

Focus on modeling:
- Agent definitions (instructions, capabilities)
- Workflow structures (chains, parallel processes, etc.)
- Execution history and state
- Resources and artifacts
- Configuration settings

#### 2. Middleware/Persistence Layer

This critical component would:
- Map database records to fast-agent configurations
- Persist agent interactions and results back to DB
- Handle state management across executions
- Provide transaction guarantees for multi-step operations

#### 3. Fork of fast-agent

Modify fast-agent to:
- Accept configurations from your persistence layer
- Report state changes and results back to your system
- Support transaction callbacks at key execution points
- Implement hooks for database-driven validation and governance

#### 4. API & Interface Layer

Provide interfaces to:
- Define and manage agents/workflows
- Execute operations
- Monitor performance
- Manage resources

## Implementation Approach

I'd recommend these specific implementation approaches:

# DB-First Multi-Agent Architecture With fast-agent

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                        API & Interface Layer                       │
└───────────────┬───────────────────────────────────────┬───────────┘
                │                                       │
                ▼                                       ▼
┌───────────────────────────┐               ┌───────────────────────┐
│    Agent Management API   │               │  Execution & Monitor  │
└───────────────┬───────────┘               └───────────┬───────────┘
                │                                       │
                ▼                                       ▼
┌───────────────────────────────────────────────────────────────────┐
│                     Middleware/Persistence Layer                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │Config Translator│  │ State Management │  │ Event Processing │  │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼─────────────────────┼──────────────────┬─┼────────────┘
            │                     │                  │ │
            ▼                     ▼                  │ │
┌───────────────────────────────────────────────────┐ │
│        Modified fast-agent (Agent Execution)      │ │
│  ┌──────────────┐  ┌───────────┐  ┌────────────┐  │ │
│  │Agent Registry│  │Workflows  │  │MCP Servers │  │ │
│  └──────────────┘  └───────────┘  └────────────┘  │ │
└───────────────────────────────────────────────────┘ │
                                                      │
                                                      ▼
┌───────────────────────────────────────────────────────────────────┐
│                           Database Layer                           │
│  ┌────────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────┐   │
│  │Agents      │  │Workflows  │  │Executions  │  │Resources    │   │
│  └────────────┘  └───────────┘  └────────────┘  └─────────────┘   │
│  ┌────────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────┐   │
│  │Configs     │  │Templates  │  │Results     │  │Metrics      │   │
│  └────────────┘  └───────────┘  └────────────┘  └─────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

## Database Schema Design

### Core Tables

1. **agents**
   - `agent_id` (PK)
   - `name`
   - `instruction`
   - `use_history`
   - `human_input`
   - `created_at`
   - `updated_at`
   - `active`

2. **agent_models**
   - `agent_model_id` (PK)
   - `agent_id` (FK)
   - `model_id` (FK)
   - `is_default`
   - `request_params` (JSON)

3. **models**
   - `model_id` (PK)
   - `provider` (anthropic, openai, etc.)
   - `name` (sonnet, o3-mini, etc.)
   - `capabilities` (JSON)
   - `cost_per_1k_tokens`

4. **agent_servers**
   - `agent_server_id` (PK)
   - `agent_id` (FK)
   - `server_id` (FK)

5. **mcp_servers**
   - `server_id` (PK)
   - `name`
   - `type` (filesystem, fetch, etc.)
   - `configuration` (JSON)
   - `sampling_model_id` (FK, nullable)

6. **workflows**
   - `workflow_id` (PK)
   - `name`
   - `type` (chain, parallel, router, etc.)
   - `instruction`
   - `configuration` (JSON - structure depends on workflow type)
   - `created_at`
   - `updated_at`
   - `active`

7. **workflow_agents**
   - `workflow_agent_id` (PK)
   - `workflow_id` (FK)
   - `agent_id` (FK)
   - `sequence_order` (for chains)
   - `role` (for specialized roles like generator/evaluator)

8. **executions**
   - `execution_id` (PK)
   - `agent_id` (FK, nullable)
   - `workflow_id` (FK, nullable)
   - `parent_execution_id` (FK, self-ref, nullable)
   - `status`
   - `started_at`
   - `completed_at`
   - `metrics` (JSON)

9. **messages**
   - `message_id` (PK)
   - `execution_id` (FK)
   - `role` (user, assistant, system)
   - `content`
   - `created_at`
   - `tokens_in`
   - `tokens_out`
   - `parent_message_id` (FK, self-ref, nullable)

10. **resources**
    - `resource_id` (PK)
    - `name`
    - `type` (image, pdf, etc.)
    - `storage_path`
    - `metadata` (JSON)
    - `created_at`

11. **prompts**
    - `prompt_id` (PK)
    - `name`
    - `template`
    - `description`
    - `created_at`
    - `updated_at`

## Implementation Details

### 1. Middleware/Persistence Layer

This layer is the bridge between your database and the fast-agent fork. Key components:

#### Config Translator
```python
class ConfigTranslator:
    def load_agent_from_db(self, agent_id: str) -> AgentConfig:
        """Convert DB agent record to fast-agent configuration"""
        agent = db.session.query(AgentModel).get(agent_id)
        servers = [server.name for server in agent.servers]
        
        return AgentConfig(
            name=agent.name,
            instruction=agent.instruction,
            servers=servers,
            model=agent.default_model.name if agent.default_model else None,
            use_history=agent.use_history,
            human_input=agent.human_input,
            request_params=self._parse_request_params(agent.default_model.request_params)
        )
    
    def load_workflow_from_db(self, workflow_id: str) -> WorkflowConfig:
        """Convert DB workflow record to fast-agent workflow configuration"""
        # Similar implementation for workflows
```

#### State Manager
```python
class StateManager:
    def create_execution(self, agent_id=None, workflow_id=None, parent_id=None) -> str:
        """Create and persist a new execution record"""
        execution = Execution(
            agent_id=agent_id,
            workflow_id=workflow_id,
            parent_execution_id=parent_id,
            status="STARTED",
            started_at=datetime.now()
        )
        db.session.add(execution)
        db.session.commit()
        return execution.execution_id
        
    def record_message(self, execution_id, role, content, parent_id=None):
        """Record a message in the current execution"""
        # Implementation
        
    def complete_execution(self, execution_id, status="COMPLETED", metrics=None):
        """Mark an execution as complete with metrics"""
        # Implementation
```

### 2. Modified fast-agent (Fork)

The key modifications to fast-agent would involve:

#### Hook System
```python
# Add to FastAgent class
def register_hooks(self, hooks):
    """Register hooks for various lifecycle events"""
    self.hooks = hooks

def _trigger_hook(self, hook_name, **kwargs):
    """Trigger a registered hook if it exists"""
    if hasattr(self, 'hooks') and hook_name in self.hooks:
        return self.hooks[hook_name](**kwargs)
    return None
```

#### DB-Aware Agent Run
```python
# Modified FastAgent.run method
async def run(self, execution_context=None):
    """Run with database execution context"""
    # Create/retrieve execution context if not provided
    if execution_context is None:
        execution_context = self._trigger_hook('before_run', agent=self)
    
    # Regular agent setup
    # ...
    
    # After setup
    self._trigger_hook('after_setup', agent=self, execution_context=execution_context)
    
    # Return modified agent wrapper that tracks messages to/from DB
    return DBTrackingAgentWrapper(agent, execution_context, self.hooks)
```

### 3. API Layer

#### Agent Management API
```python
@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent definition"""
    data = request.json
    
    # Create DB records
    agent = Agent(
        name=data['name'],
        instruction=data['instruction'],
        use_history=data.get('use_history', True),
        human_input=data.get('human_input', False)
    )
    db.session.add(agent)
    db.session.commit()
    
    # Associate servers
    for server_name in data.get('servers', []):
        server = db.session.query(MCPServer).filter_by(name=server_name).first()
        if server:
            agent_server = AgentServer(agent_id=agent.agent_id, server_id=server.server_id)
            db.session.add(agent_server)
    
    # Set model
    if 'model' in data:
        model = db.session.query(Model).filter_by(name=data['model']).first()
        if model:
            agent_model = AgentModel(
                agent_id=agent.agent_id,
                model_id=model.model_id,
                is_default=True,
                request_params=data.get('request_params', {})
            )
            db.session.add(agent_model)
    
    db.session.commit()
    return jsonify({"agent_id": agent.agent_id})

# Similar endpoints for workflows, executions, etc.
```

#### Execution API
```python
@app.route('/api/execute', methods=['POST'])
async def execute():
    """Execute an agent or workflow"""
    data = request.json
    
    # Initialize system components
    config_translator = ConfigTranslator()
    state_manager = StateManager()
    
    # Create DB execution record
    execution_id = state_manager.create_execution(
        agent_id=data.get('agent_id'),
        workflow_id=data.get('workflow_id')
    )
    
    # Set up hooks
    hooks = {
        'message_sent': state_manager.record_message,
        'execution_complete': state_manager.complete_execution
    }
    
    # Load agent/workflow from DB
    if 'agent_id' in data:
        agent_config = config_translator.load_agent_from_db(data['agent_id'])
        fast_agent = FastAgent()
        fast_agent.register_hooks(hooks)
        
        # Create agent dynamically
        @fast_agent.agent(**agent_config)
        async def dynamic_agent():
            async with fast_agent.run(execution_id) as agent:
                return await agent.send(data['message'])
                
        result = await dynamic_agent()
        return jsonify({"result": result, "execution_id": execution_id})
    
    # Similar implementation for workflows
```

## Advantages of This Approach

1. **Database as Single Source of Truth**: All configurations, states, and results are stored in a structured database
2. **Versioning and Auditing**: Native support for versioning agent definitions and execution history
3. **Scalability**: Database transactions handle concurrent operations and state management
4. **Flexibility**: Easy to extend with additional database tables for specific needs
5. **Monitoring and Analytics**: Rich data model supports comprehensive analytics
6. **Integration Point**: Natural integration point for other systems via the database

## Tradeoffs and Considerations

1. **Performance**: Database operations add overhead to execution - consider caching strategies
2. **Complexity**: More moving parts than a pure in-memory approach
3. **Migration Path**: Need to carefully fork fast-agent to maintain compatibility with upstream changes
4. **Transaction Management**: Must handle transaction boundaries carefully, especially with long-running operations



code examples:

```python
'''
DB-FIRST FAST-AGENT INTEGRATION
Key implementation files for the architecture
'''

# 1. Database Models (using SQLAlchemy)
# --------------------------------------
# models.py

from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Agent(Base):
    __tablename__ = 'agents'
    
    agent_id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    instruction = Column(Text, nullable=False)
    use_history = Column(Boolean, default=True)
    human_input = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    # Relationships
    models = relationship("AgentModel", back_populates="agent")
    servers = relationship("MCPServer", secondary="agent_servers", back_populates="agents")
    executions = relationship("Execution", back_populates="agent")
    
    @property
    def default_model(self):
        """Return the default model for this agent"""
        for model in self.models:
            if model.is_default:
                return model
        return None if not self.models else self.models[0]


class Model(Base):
    __tablename__ = 'models'
    
    model_id = Column(String(36), primary_key=True)
    provider = Column(String(50), nullable=False)
    name = Column(String(50), nullable=False)
    capabilities = Column(JSON, default={})
    cost_per_1k_tokens = Column(Float, default=0.0)
    
    # Relationships
    agent_models = relationship("AgentModel", back_populates="model")


class AgentModel(Base):
    __tablename__ = 'agent_models'
    
    agent_model_id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey('agents.agent_id'), nullable=False)
    model_id = Column(String(36), ForeignKey('models.model_id'), nullable=False)
    is_default = Column(Boolean, default=False)
    request_params = Column(JSON, default={})
    
    # Relationships
    agent = relationship("Agent", back_populates="models")
    model = relationship("Model", back_populates="agent_models")


class MCPServer(Base):
    __tablename__ = 'mcp_servers'
    
    server_id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    configuration = Column(JSON, default={})
    sampling_model_id = Column(String(36), ForeignKey('models.model_id'), nullable=True)
    
    # Relationships
    agents = relationship("Agent", secondary="agent_servers", back_populates="servers")
    sampling_model = relationship("Model")


class AgentServer(Base):
    __tablename__ = 'agent_servers'
    
    agent_server_id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey('agents.agent_id'), nullable=False)
    server_id = Column(String(36), ForeignKey('mcp_servers.server_id'), nullable=False)


class Workflow(Base):
    __tablename__ = 'workflows'
    
    workflow_id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    instruction = Column(Text, nullable=True)
    configuration = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    # Relationships
    agents = relationship("Agent", secondary="workflow_agents")
    executions = relationship("Execution", back_populates="workflow")


class WorkflowAgent(Base):
    __tablename__ = 'workflow_agents'
    
    workflow_agent_id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), ForeignKey('workflows.workflow_id'), nullable=False)
    agent_id = Column(String(36), ForeignKey('agents.agent_id'), nullable=False)
    sequence_order = Column(Integer, nullable=True)
    role = Column(String(50), nullable=True)


class Execution(Base):
    __tablename__ = 'executions'
    
    execution_id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey('agents.agent_id'), nullable=True)
    workflow_id = Column(String(36), ForeignKey('workflows.workflow_id'), nullable=True)
    parent_execution_id = Column(String(36), ForeignKey('executions.execution_id'), nullable=True)
    status = Column(String(20), default='PENDING')
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    metrics = Column(JSON, default={})
    
    # Relationships
    agent = relationship("Agent", back_populates="executions")
    workflow = relationship("Workflow", back_populates="executions")
    parent_execution = relationship("Execution", remote_side=[execution_id])
    child_executions = relationship("Execution")
    messages = relationship("Message", back_populates="execution")


class Message(Base):
    __tablename__ = 'messages'
    
    message_id = Column(String(36), primary_key=True)
    execution_id = Column(String(36), ForeignKey('executions.execution_id'), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    parent_message_id = Column(String(36), ForeignKey('messages.message_id'), nullable=True)
    
    # Relationships
    execution = relationship("Execution", back_populates="messages")
    parent_message = relationship("Message", remote_side=[message_id])
    child_messages = relationship("Message")


class Resource(Base):
    __tablename__ = 'resources'
    
    resource_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class Prompt(Base):
    __tablename__ = 'prompts'
    
    prompt_id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    template = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 2. Modified FastAgent Core
# --------------------------------------
# db_fastagent.py

import uuid
from typing import Dict, Any, Callable, Optional, List
from mcp_agent.core.fastagent import FastAgent as OriginalFastAgent
from mcp_agent.core.agent import Agent

class ExecutionContext:
    """Context object for tracking DB-related execution information"""
    
    def __init__(self, execution_id: str, parent_execution_id: Optional[str] = None):
        self.execution_id = execution_id
        self.parent_execution_id = parent_execution_id
        self.child_contexts = {}
    
    def create_child_context(self, agent_name: str = None, workflow_name: str = None):
        """Create a child execution context"""
        # This would typically involve a DB operation
        # For simplicity, we're just creating a new context object
        child_execution_id = str(uuid.uuid4())
        child_context = ExecutionContext(child_execution_id, self.execution_id)
        
        # Store reference to child context
        key = agent_name or workflow_name or child_execution_id
        self.child_contexts[key] = child_context
        
        return child_context


class DBTrackingAgentWrapper:
    """Wraps a fast-agent Agent to track interactions with the database"""
    
    def __init__(self, agent: Agent, execution_context: ExecutionContext, hooks: Dict[str, Callable]):
        self.agent = agent
        self.execution_context = execution_context
        self.hooks = hooks
        
        # Proxy attributes from the wrapped agent
        for attr_name in dir(agent):
            if not attr_name.startswith('_') and attr_name not in ['send', 'prompt', 'interactive']:
                setattr(self, attr_name, getattr(agent, attr_name))
    
    async def send(self, message: str):
        """Send a message to the agent and record it in the database"""
        # Record user message
        if 'message_sent' in self.hooks:
            self.hooks['message_sent'](
                execution_id=self.execution_context.execution_id,
                role='user',
                content=message
            )
        
        # Process with agent
        response = await self.agent.send(message)
        
        # Record assistant response
        if 'message_sent' in self.hooks:
            self.hooks['message_sent'](
                execution_id=self.execution_context.execution_id,
                role='assistant',
                content=response
            )
        
        return response
    
    async def prompt(self, default_prompt: str = None):
        """Start an interactive prompt session"""
        # Similar implementation to send but for prompt
        # ...
        
    async def interactive(self):
        """Start an interactive chat session"""
        # Similar implementation recording all interactions
        # ...


class DBFastAgent(OriginalFastAgent):
    """FastAgent extension that integrates with a database backend"""
    
    def __init__(self, app_name: str = "DB Fast Agent"):
        super().__init__(app_name)
        self.hooks = {}
    
    def register_hooks(self, hooks: Dict[str, Callable]):
        """Register hooks for various lifecycle events"""
        self.hooks = hooks
    
    def _trigger_hook(self, hook_name: str, **kwargs) -> Any:
        """Trigger a registered hook if it exists"""
        if hook_name in self.hooks:
            return self.hooks[hook_name](**kwargs)
        return None
    
    async def run(self, execution_context: ExecutionContext = None):
        """Run with database execution context"""
        # Create/retrieve execution context if not provided
        if execution_context is None and 'before_run' in self.hooks:
            execution_context = self.hooks['before_run'](agent=self)
        
        # Regular agent setup from original FastAgent
        agent = await super().run()
        
        # After setup
        if 'after_setup' in self.hooks:
            self.hooks['after_setup'](agent=agent, execution_context=execution_context)
        
        # Return modified agent wrapper that tracks messages to/from DB
        return DBTrackingAgentWrapper(agent, execution_context, self.hooks)
    
    # Override other methods as needed to integrate with DB


# 3. Middleware Layer
# --------------------------------------
# persistence.py

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional, Tuple
import uuid
from datetime import datetime
import json

from models import Agent as AgentModel
from models import Workflow as WorkflowModel
from models import Execution, Message, MCPServer, Model, AgentModel as AgentModelLink

class ConfigTranslator:
    """Translates between database models and fast-agent configurations"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def load_agent_from_db(self, agent_id: str) -> Dict[str, Any]:
        """Convert DB agent record to fast-agent configuration"""
        agent = self.db.query(AgentModel).filter_by(agent_id=agent_id).first()
        
        if not agent:
            raise ValueError(f"Agent with ID {agent_id} not found")
        
        # Get servers
        servers = [server.name for server in agent.servers]
        
        # Get default model
        default_model = agent.default_model
        model_name = default_model.model.name if default_model else None
        
        # Parse request params
        request_params = {}
        if default_model and default_model.request_params:
            request_params = default_model.request_params
        
        return {
            "name": agent.name,
            "instruction": agent.instruction,
            "servers": servers,
            "model": model_name,
            "use_history": agent.use_history,
            "human_input": agent.human_input,
            "request_params": request_params
        }
    
    def load_workflow_from_db(self, workflow_id: str) -> Dict[str, Any]:
        """Convert DB workflow record to fast-agent workflow configuration"""
        workflow = self.db.query(WorkflowModel).filter_by(workflow_id=workflow_id).first()
        
        if not workflow:
            raise ValueError(f"Workflow with ID {workflow_id} not found")
        
        # Base config that all workflows share
        config = {
            "name": workflow.name,
            "instruction": workflow.instruction,
        }
        
        # Add workflow-specific configuration
        config.update(workflow.configuration)
        
        return config


class StateManager:
    """Manages execution state in the database"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_execution(self, 
                         agent_id: Optional[str] = None, 
                         workflow_id: Optional[str] = None, 
                         parent_id: Optional[str] = None) -> str:
        """Create and persist a new execution record"""
        execution_id = str(uuid.uuid4())
        
        execution = Execution(
            execution_id=execution_id,
            agent_id=agent_id,
            workflow_id=workflow_id,
            parent_execution_id=parent_id,
            status="STARTED",
            started_at=datetime.utcnow()
        )
        
        self.db.add(execution)
        self.db.commit()
        
        # Create an execution context object
        context = ExecutionContext(execution_id, parent_id)
        
        return context
    
    def record_message(self, 
                       execution_id: str, 
                       role: str, 
                       content: str,
                       parent_id: Optional[str] = None,
                       tokens_in: int = 0,
                       tokens_out: int = 0) -> str:
        """Record a message in the current execution"""
        message_id = str(uuid.uuid4())
        
        message = Message(
            message_id=message_id,
            execution_id=execution_id,
            role=role,
            content=content,
            parent_message_id=parent_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out
        )
        
        self.db.add(message)
        self.db.commit()
        
        return message_id
    
    def complete_execution(self, 
                           execution_id: str, 
                           status: str = "COMPLETED", 
                           metrics: Optional[Dict[str, Any]] = None) -> None:
        """Mark an execution as complete with metrics"""
        execution = self.db.query(Execution).filter_by(execution_id=execution_id).first()
        
        if execution:
            execution.status = status
            execution.completed_at = datetime.utcnow()
            
            if metrics:
                execution.metrics = metrics
            
            self.db.commit()


# 4. API Layer
# --------------------------------------
# api.py

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import uuid
from sqlalchemy.orm import Session

from db_connection import get_db
from persistence import ConfigTranslator, StateManager
from db_fastagent import DBFastAgent
from models import Agent as AgentModel, Workflow as WorkflowModel

# Pydantic models for API requests/responses
class AgentCreate(BaseModel):
    name: str
    instruction: str
    servers: Optional[List[str]] = []
    model: Optional[str] = None
    use_history: Optional[bool] = True
    human_input: Optional[bool] = False
    request_params: Optional[Dict[str, Any]] = {}

class AgentResponse(BaseModel):
    agent_id: str

class ExecuteRequest(BaseModel):
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    message: str

class ExecuteResponse(BaseModel):
    execution_id: str
    result: str

# Create FastAPI application
app = FastAPI(title="DB-First Multi-Agent Framework")

# Agent management endpoints
@app.post("/api/agents", response_model=AgentResponse)
async def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db)
):
    """Create a new agent in the database"""
    agent_id = str(uuid.uuid4())
    
    # Create DB records
    # This is simplified - in a real implementation you'd handle
    # all the relationships and validations
    agent = AgentModel(
        agent_id=agent_id,
        name=agent_data.name,
        instruction=agent_data.instruction,
        use_history=agent_data.use_history,
        human_input=agent_data.human_input
    )
    
    db.add(agent)
    db.commit()
    
    # Additional steps to link servers, models, etc. would happen here
    # ...
    
    return {"agent_id": agent_id}

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get agent details"""
    agent = db.query(AgentModel).filter_by(agent_id=agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Convert to dictionary and return
    # In a real implementation, use a proper schema for the response
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "instruction": agent.instruction,
        "use_history": agent.use_history,
        "human_input": agent.human_input,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
        "active": agent.active
    }

# Similar endpoints for workflows, resources, etc.
# ...

# Execution endpoints
@app.post("/api/execute", response_model=ExecuteResponse)
async def execute_agent_or_workflow(
    request: ExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Execute an agent or workflow with a message"""
    if not request.agent_id and not request.workflow_id:
        raise HTTPException(
            status_code=400, 
            detail="Either agent_id or workflow_id must be provided"
        )
    
    # Initialize components
    config_translator = ConfigTranslator(db)
    state_manager = StateManager(db)
    
    # Create execution record and context
    if request.agent_id:
        execution_context = state_manager.create_execution(agent_id=request.agent_id)
    else:
        execution_context = state_manager.create_execution(workflow_id=request.workflow_id)
    
    # Set up hooks for DB integration
    hooks = {
        'message_sent': state_manager.record_message,
        'execution_complete': state_manager.complete_execution
    }
    
    # Execute in background to avoid blocking the API
    if request.agent_id:
        background_tasks.add_task(
            execute_agent_in_background,
            agent_id=request.agent_id,
            message=request.message,
            execution_context=execution_context,
            config_translator=config_translator,
            hooks=hooks
        )
    else:
        background_tasks.add_task(
            execute_workflow_in_background,
            workflow_id=request.workflow_id,
            message=request.message,
            execution_context=execution_context,
            config_translator=config_translator,
            hooks=hooks
        )
    
    # Return immediately with execution ID
    # Client can poll for results with a separate endpoint
    return {
        "execution_id": execution_context.execution_id,
        "result": "Execution started" 
    }

@app.get("/api/executions/{execution_id}")
async def get_execution_status(execution_id: str, db: Session = Depends(get_db)):
    """Get the status and results of an execution"""
    # Retrieve execution from database
    # In a real implementation, include messages and other details
    # ...
    
    return {
        "execution_id": execution_id,
        "status": "COMPLETED",  # Example - would come from DB
        "messages": []  # Would include messages from DB
    }

# Background task functions
async def execute_agent_in_background(
    agent_id: str, 
    message: str,
    execution_context,
    config_translator,
    hooks
):
    """Execute an agent in the background"""
    try:
        # Load agent config from database
        agent_config = config_translator.load_agent_from_db(agent_id)
        
        # Create DBFastAgent instance
        fast_agent = DBFastAgent()
        fast_agent.register_hooks(hooks)
        
        # Dynamically create and run the agent
        @fast_agent.agent(**agent_config)
        async def dynamic_agent():
            async with fast_agent.run(execution_context) as agent:
                result = await agent.send(message)
                # Mark execution as complete
                hooks['execution_complete'](
                    execution_id=execution_context.execution_id,
                    status="COMPLETED",
                    metrics={"success": True}
                )
                return result
        
        await dynamic_agent()
        
    except Exception as e:
        # Log error and mark execution as failed
        if 'execution_complete' in hooks:
            hooks['execution_complete'](
                execution_id=execution_context.execution_id,
                status="FAILED",
                metrics={"error": str(e)}
            )
        raise

async def execute_workflow_in_background(
    workflow_id: str, 
    message: str,
    execution_context,
    config_translator,
    hooks
):
    """Execute a workflow in the background"""
    # Similar to execute_agent_in_background but for workflows
    # ...

# 5. Database Connection
# --------------------------------------
# db_connection.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL - replace with your actual database URL
DATABASE_URL = "postgresql://username:password@localhost/dbname"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 6. Main Application
# --------------------------------------
# main.py

import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api import app as api_app

# Add CORS middleware
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # Start the FastAPI server
    uvicorn.run(api_app, host="0.0.0.0", port=8000)

# 7. CLI Interface
# --------------------------------------
# cli.py

import click
import asyncio
import json
import os
from sqlalchemy.orm import Session

from db_connection import get_db, SessionLocal
from persistence import ConfigTranslator, StateManager
from db_fastagent import DBFastAgent

@click.group()
def cli():
    """DB-First Multi-Agent Framework CLI"""
    pass

@cli.command()
@click.option('--agent-id', required=True, help='ID of the agent to run')
@click.option('--message', required=True, help='Message to send to the agent')
def run_agent(agent_id, message):
    """Run an agent from the database with a message"""
    db = SessionLocal()
    
    try:
        # Initialize components
        config_translator = ConfigTranslator(db)
        state_manager = StateManager(db)
        
        # Create execution context
        execution_context = state_manager.create_execution(agent_id=agent_id)
        
        # Set up hooks
        hooks = {
            'message_sent': state_manager.record_message,
            'execution_complete': state_manager.complete_execution
        }
        
        # Load agent config
        agent_config = config_translator.load_agent_from_db(agent_id)
        
        # Create fast agent instance
        fast_agent = DBFastAgent()
        fast_agent.register_hooks(hooks)
        
        # Define and run agent
        @fast_agent.agent(**agent_config)
        async def dynamic_agent():
            async with fast_agent.run(execution_context) as agent:
                result = await agent.send(message)
                click.echo(f"Result: {result}")
                return result
        
        # Run the agent
        asyncio.run(dynamic_agent())
        
    finally:
        db.close()

@cli.command()
@click.option('--agent-id', required=True, help='ID of the agent to chat with')
def chat(agent_id):
    """Start an interactive chat with an agent"""
    db = SessionLocal()
    
    try:
        # Initialize components
        config_translator = ConfigTranslator(db)
        state_manager = StateManager(db)
        
        # Create execution context
        execution_context = state_manager.create_execution(agent_id=agent_id)
        
        # Set up hooks
        hooks = {
            'message_sent': state_manager.record_message,
            'execution_complete': state_manager.complete_execution
        }
        
        # Load agent config
        agent_config = config_translator.load_agent_from_db(agent_id)
        
        # Create fast agent instance
        fast_agent = DBFastAgent()
        fast_agent.register_hooks(hooks)
        
        # Define and run agent in interactive mode
        @fast_agent.agent(**agent_config)
        async def dynamic_agent():
            async with fast_agent.run(execution_context) as agent:
                click.echo(f"Starting chat with agent: {agent_config['name']}")
                await agent.interactive()
        
        # Run the agent
        asyncio.run(dynamic_agent())
        
    finally:
        db.close()

if __name__ == '__main__':
    cli()
```

# Integration Guide & Best Practices

## Forking fast-agent

When integrating fast-agent into your DB-first multi-agent framework, follow these guidelines to maintain compatibility while adding your database-centric features.

### Fork Strategy

1. **Minimal Core Changes**
   - Focus modifications on adding hook points rather than changing core logic
   - Create wrapper classes where possible instead of modifying original classes
   - Keep a clean separation between fast-agent and your database components

2. **Tracking Upstream**
   - Regularly sync with the upstream fast-agent repository
   - Structure your changes to make merges easier
   - Use feature flags to enable/disable DB integration features

3. **Testing Strategy**
   - Set up parallel test suites: one for vanilla fast-agent compatibility, one for your DB integration
   - Use mock databases for testing to avoid external dependencies
   - Test upgrade paths to ensure smooth version transitions

## Database Design Considerations

### Schema Evolution

As your system evolves, you'll need to update your database schema. Consider:

1. **Migration Strategy**
   - Use a migration tool like Alembic with SQLAlchemy
   - Version all schema changes
   - Support rollback procedures for failed migrations

2. **Performance Indexes**
   - Index frequently queried fields like agent_id, execution_id
   - Consider composite indexes for common query patterns
   - Add partial indexes for filtering on active/inactive records

3. **Data Archiving**
   - Implement a strategy for archiving old executions and messages
   - Consider partitioning tables by time for large datasets
   - Define data retention policies based on business needs

## Performance Optimization

### Database Access Patterns

1. **Connection Pooling**
   - Configure appropriate connection pool sizes
   - Monitor connection usage patterns
   - Consider read replicas for high-read scenarios

2. **Batch Operations**
   - Batch inserts for messages when possible
   - Use bulk updates for status changes
   - Consider asynchronous DB operations for non-critical paths

3. **Caching Strategy**
   - Cache frequently accessed agent and workflow definitions
   - Implement a TTL-based invalidation strategy
   - Consider Redis or similar for distributed caching

### Scaling Considerations

1. **Horizontal Scaling**
   - Ensure your database choice supports horizontal scaling
   - Consider sharding strategies (by tenant, by time, etc.)
   - Design with eventual consistency in mind for distributed operations

2. **Execution Isolation**
   - Run agent executions in isolated processes or containers
   - Implement resource limits and timeouts
   - Consider serverless execution models for bursty workloads

## Integration Patterns

### Event-Driven Architecture

Consider evolving to an event-driven architecture:

1. **Message Queue Integration**
   - Use a message queue (RabbitMQ, Kafka) for execution requests
   - Implement event sourcing for execution history
   - Enable asynchronous workflows across multiple systems

2. **Webhooks and Callbacks**
   - Support webhooks for execution completion
   - Implement callback URLs for long-running operations
   - Enable integrations with external systems

### Multi-Tenancy Support

If supporting multiple tenants (users/organizations):

1. **Tenant Isolation**
   - Add tenant_id to all relevant tables
   - Implement row-level security in the database
   - Consider database schema isolation for high-security requirements

2. **Resource Quotas**
   - Implement usage tracking per tenant
   - Set configurable limits on executions, tokens, etc.
   - Support fair resource allocation under load

## Operational Considerations

### Monitoring and Observability

1. **Metrics Collection**
   - Track execution times, token usage, error rates
   - Monitor database performance metrics
   - Set up alerting for anomalies

2. **Logging Strategy**
   - Implement structured logging
   - Consider log aggregation solutions
   - Balance verbosity with performance impact

3. **Tracing**
   - Implement distributed tracing across execution flows
   - Track requests from API through execution
   - Visualize complex workflow patterns

### Security Considerations

1. **Authentication & Authorization**
   - Implement proper authentication for API access
   - Define granular permissions for agent/workflow access
   - Secure database credentials and connection strings

2. **Data Privacy**
   - Implement encryption for sensitive data
   - Consider data minimization principles
   - Support data export and deletion capabilities

3. **Audit Trails**
   - Record who created/modified agents and workflows
   - Track usage patterns for compliance purposes
   - Implement tamper-evident logging for sensitive operations

## Development Workflow

### Local Development

1. **Development Environment**
   - Use Docker Compose for local database and dependencies
   - Implement environment-specific configurations
   - Support developer-specific overrides

2. **Test Data Generation**
   - Create scripts to populate test agents and workflows
   - Implement sample execution data generation
   - Support importing/exporting configurations

### CI/CD Pipeline

1. **Automated Testing**
   - Run database migration tests
   - Execute integration tests with test databases
   - Verify upstream compatibility

2. **Deployment Strategy**
   - Implement blue/green deployments
   - Support database schema migrations as part of deployment
   - Include rollback procedures

## Migration Path from fast-agent

If you're migrating an existing fast-agent implementation:

1. **Incremental Migration**
   - Start by importing existing agents/workflows into the database
   - Map YAML configurations to database records
   - Support both file-based and DB-based configurations initially

2. **Hybrid Operation**
   - Allow fallback to file-based configuration when DB is unavailable
   - Create utilities to sync between file and database configurations
   - Provide tools to validate configuration consistency

3. **Conversion Tools**
   - Build tools to export DB configurations to YAML
   - Support importing YAML configurations into the database
   - Create verification tools to validate consistency

## System Architecture Alternatives

### Microservices Approach

For larger implementations, consider:

1. **Service Decomposition**
   - Separate agent definition service
   - Dedicated execution service
   - Isolated analytics service

2. **API Gateway**
   - Implement an API gateway for service coordination
   - Handle authentication and request routing
   - Manage rate limiting and quotas

### Serverless Architecture

For variable workloads:

1. **Function-as-a-Service**
   - Deploy agent executions as serverless functions
   - Scale automatically with demand
   - Pay only for actual execution time

2. **Managed Services**
   - Use managed database services
   - Leverage cloud provider message queues
   - Implement with minimal operational overhead

Let me finish the API layer implementation and provide some additional insights on integrating fast-agent with your database-first approach.

Your question touches on an interesting architectural challenge. Let me walk you through my recommended approach for creating a DB-first multi-agent framework that effectively integrates with fast-agent.

## Core Architecture Strategy

Based on the fast-agent documentation you shared and your RDBMS background, I've designed a layered architecture that puts your database at the center while leveraging fast-agent's capabilities:

1. **Database Layer** - Your source of truth for all agent definitions, workflows, executions, and results
2. **Middleware/Persistence Layer** - Translates between database records and fast-agent objects
3. **Modified fast-agent** - A fork that adds DB integration points without breaking core functionality
4. **API/Interface Layer** - External interfaces to your system

This approach gives you high cohesion by cleanly separating concerns while accepting the tradeoff of tighter coupling between the database and agent execution layers.

## Key Elements of the Solution

### 1. Database Schema Design

I've designed a comprehensive schema that models:
- Agent definitions with their instructions and capabilities
- Workflow structures (chains, evaluator-optimizers, etc.)
- Execution history with detailed message tracking
- Resources and configurational elements

The schema follows relational best practices while supporting the rich object model needed for agent interactions.

### 2. Modified fast-agent Fork

Rather than just using fast-agent as-is, the recommended approach is to fork it and add:

- A hook system to integrate with your database at key execution points
- Wrapper classes that handle database operations transparently
- Support for database-sourced configurations

This approach minimizes changes to fast-agent core logic while enabling deep integration with your database.

### 3. Middleware Integration Layer

The critical "glue" between your database and fast-agent is a translation layer that:
- Maps database records to fast-agent configurations
- Translates database representations of workflows to fast-agent execution structures
- Persists execution results and metrics back to the database
- Manages state transitions and history

## Implementation Benefits

This architecture offers several advantages:

1. **Database as Source of Truth** - All agent configurations, states, and results persist in your database
2. **Transaction Integrity** - Database transactions provide ACID guarantees for agent operations
3. **Rich Querying** - Leverage SQL's power for analyzing agent performance and behavior
4. **Version Control** - Track changes to agent configurations over time
5. **Multi-user Support** - Built-in support for concurrent users and permissions

## Tradeoffs & Considerations

Some important considerations with this approach:

1. **Performance Overhead** - Database operations add latency compared to in-memory execution
2. **Complexity** - More moving parts to maintain and debug
3. **Upstream Compatibility** - Need to regularly merge changes from fast-agent upstream

## Next Steps

If you decide to pursue this architecture, I would recommend:

1. Start with implementing the database schema and basic persistence layer
2. Fork fast-agent and implement the hook system
3. Build a simple proof-of-concept with a single agent type
4. Gradually extend to support all fast-agent workflow types

Would you like me to elaborate on any specific aspect of this architecture? For example, I could dive deeper into the database schema design, the hook system implementation, or strategies for maintaining compatibility with upstream fast-agent.

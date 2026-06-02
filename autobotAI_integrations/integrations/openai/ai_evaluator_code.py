from pydantic import BaseModel, Field
from typing import List
import json, re
from pydantic_ai.settings import ModelSettings
from pydantic_ai.exceptions import ModelHTTPError
import logging

logger = logging.getLogger(__name__)

def estimate_tokens(text: str) -> int:
    """
    Rough estimation of tokens from text.
    OpenAI models roughly use 1 token per 4 characters on average.
    """
    return int(len(str(text)) / 4) + 50  # +50 for overhead


async def executor(context):
    agent = context["clients"]["Agent"]
    prompt = context["params"]["prompt"]
    model = context["params"]["model"]
    resources = json.loads(json.dumps(context["params"]["resources"], default=str))
    MAX_TOKEN = context['params'].get('output_token', 25000)

    if not isinstance(resources, list):
        resources = [resources]
    
    # Better token limit management
    # Keep 30% buffer for safety (input + output + overhead)
    SAFE_INPUT_TOKENS = int(MAX_TOKEN * 0.6)
    SYSTEM_PROMPT_TOKENS = 2500  # Approximate tokens for system prompt
    
    try:
        current_token_count = SYSTEM_PROMPT_TOKENS + estimate_tokens(prompt)
        parsable_resources_count = 0
        
        for resource in resources:
            resource_tokens = estimate_tokens(str(resource))
            if current_token_count + resource_tokens < SAFE_INPUT_TOKENS:
                parsable_resources_count += 1
                current_token_count += resource_tokens
            else:
                logger.warning(f"Skipping resource due to token limit. Current: {current_token_count}, "
                             f"Adding: {resource_tokens}, Safe limit: {SAFE_INPUT_TOKENS}")
                break
        
        # Ensure we have at least 1 resource, even if it exceeds limit slightly
        if parsable_resources_count == 0 and len(resources) > 0:
            logger.warning(f"All resources exceed token limit. Using first resource anyway.")
            parsable_resources_count = 1
        
        resources = resources[: min(parsable_resources_count, 10)]
        logger.info(f"Using {len(resources)} resources. Token count: {current_token_count}/{SAFE_INPUT_TOKENS}")
        
        if len(resources) == 0:
            logger.error("No resources available after filtering. Original resources: {len(resources)}")
        
    except Exception as e:
        logger.warning(f"Error in token calculation: {e}. Using all resources.")
        pass

    class ResourceEvaluation(BaseModel):
        name: str = Field(..., description="Matches unique resource 'name' field")
        action_required: bool = Field(..., description="Whether action is required")
        probability_score: int = Field(..., ge=1, le=100, description="Probability score between 1 and 100")
        confidence_score: int = Field(..., ge=0, le=100, description="Confidence score between 0 and 100")
        reason: str = Field(..., description="Explanation for the scores")
        fields_evaluated: List[str] = Field(..., description="List of fields that were evaluated")


    system_prompt = f"""You are an AI evaluator that returns decision-making JSON data only.Given the prompt and resource list, evaluate each resource based on the following field descriptions:\n
    1. **name**: The unique name of the resource being evaluated. It should match exactly with the resource 'name' field value.\n
    2. **action_required**: A Boolean indicating whether action is advisable for the resource. Determine this based on `probability_score` and `confidence_score`. Return `true` if action is recommended; otherwise, return `false`.\n
    3. **probability_score**: An integer (1-100) representing the likelihood of a specific outcome occurring. Higher scores suggest automation or action; lower scores suggest manual intervention or no action.\n
    4. **confidence_score**: An integer (0-100) reflecting the confidence in the evaluation's accuracy. Lower scores imply that more assumptions were needed to reach the result.\n
    5. **reason**: A textual explanation justifying the `action_required` value, based on the `probability_score` and `confidence_score`.\n
    6. **fields_evaluated**: A list of the field names considered in determining the above values.\n

    Your response must be a JSON array with one object per resource, strictly following this schema: {ResourceEvaluation.model_json_schema()}

    Rules:\n
    - Return only a JSON array, structured for direct parsing using `json.loads(response)` in Python.\n
    - No extra text, symbols, or markdown.\n
    - Each object must contain all required fields."""

    user_prompt = f"""
    Resources: {resources}
    Prompt: {prompt}"""

    agent_instance = agent(model,system_prompt=system_prompt,model_settings=ModelSettings(max_tokens=MAX_TOKEN))

    # Execute agent with retry logic for token limit errors
    max_retries = 3
    retry_count = 0
    current_resources = resources[:]
    last_error = None
    
    logger.info(f"Starting agent execution with {len(current_resources)} resources")
    
    while retry_count < max_retries:
        try:
            user_prompt = f"""
            Resources: {current_resources}
            Prompt: {prompt}"""
            
            logger.info(f"Attempt {retry_count + 1}/{max_retries} with {len(current_resources)} resources")
            result = await agent_instance.run(user_prompt)
            
            generated_text = result.output
            logger.info(f"Agent response received: {len(generated_text)} characters")
            
            try:
                try:
                    results = json.loads(generated_text)
                except json.decoder.JSONDecodeError as e:
                    # Search for the first occurrence of text inside triple backticks
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", generated_text, re.DOTALL)
                    if match:
                        results = json.loads(match.group(1).strip())
                    else:
                        raise e
                
                logger.info(f"Parsed {len(results) if isinstance(results, list) else 1} decision(s) from agent")
                return combine_resources_with_decision(current_resources, results)
                
            except Exception as e:
                logger.error(f"Error processing agent response: {str(e)}")
                return {
                    "error": str(e),
                    "evaluated-response": str(generated_text)[:500],  # Truncate to avoid huge responses
                }
                
        except ModelHTTPError as e:
            last_error = e
            error_str = str(e).lower()
            # Check if it's a token limit error
            if "too long" in error_str or "input is too long" in error_str or "exceeds" in error_str:
                logger.warning(f"Input too long error on attempt {retry_count + 1}. Reducing resources...")
                if len(current_resources) > 1:
                    # Reduce resources by 50%
                    current_resources = current_resources[:max(1, len(current_resources) // 2)]
                    retry_count += 1
                    logger.info(f"Retry {retry_count}: Using {len(current_resources)} resources")
                    continue
                else:
                    # Can't reduce further
                    logger.error("Cannot reduce resources further (already at 1 resource)")
                    break
            else:
                # Different error, don't retry
                logger.error(f"Non-recoverable ModelHTTPError: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error on attempt {retry_count + 1}: {str(e)}")
            last_error = e
            break
    
    # If we exhausted retries or hit a non-recoverable error
    if last_error:
        error_message = str(last_error)
        if isinstance(last_error, ModelHTTPError):
            if hasattr(last_error, 'body') and isinstance(last_error.body, dict):
                error_message = last_error.body.get('message', str(last_error))
        
        logger.error(f"Failed after {retry_count} attempts: {error_message}")
        return {
            "error": f"Failed to evaluate resources after {retry_count} attempts: {error_message}",
            "attempted_with_resources": len(current_resources),
            "resources_sent": current_resources[:1] if current_resources else [],
            "note": "Input was too long even with reduced resources. Consider:\n"
                   "1. Reducing resource payload size\n"
                   "2. Increasing output_token parameter\n"
                   "3. Using a model with higher token limits\n"
                   "4. Processing resources in smaller batches"
        }


def combine_resources_with_decision(resources, decisions):
    results = []
    if isinstance(decisions, dict):
        decisions = [decisions]
    for resource in resources:
        for decision in decisions:
            if resource["name"] == decision["name"]:
                resource["decision"] = decision
                results.append(resource)
                break
    if results:
        return results
    else:
        raise Exception("Something Went Wrong, Please try again.")
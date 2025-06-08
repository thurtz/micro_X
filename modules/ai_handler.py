# --- API DOCUMENTATION for modules/ai_handler.py ---
#
# **Purpose:** Handles all interactions with Ollama LLMs for translating natural
# language to commands, validating command syntax, and explaining commands.
#
# **Public Functions:**
#
# async def is_valid_linux_command_according_to_ai(command_text: str, config_param: dict) -> bool | None:
#     """
#     Asks the Validator AI model if the given text is a likely Linux command.
#
#     Performs multiple validation attempts as configured and returns a boolean
#     based on a majority vote of the AI's 'yes'/'no' responses.
#
#     Args:
#         command_text (str): The string to validate.
#         config_param (dict): The main application configuration object.
#
#     Returns:
#         bool | None: True if the AI considers it a command, False if not.
#                      None if the result is inconclusive after all attempts.
#     """
#
# async def get_validated_ai_command(human_query: str, config_param: dict, append_output_func: callable, get_app_func: callable) -> tuple[str | None, str | None]:
#     """
#     The main entry point to translate a natural language query into a validated shell command.
#
#     This function orchestrates a multi-step process:
#     1. It tries the 'primary_translator' AI to get a command.
#     2. If successful, it validates the command using `is_valid_linux_command_according_to_ai`.
#     3. If the primary translator fails or validation fails, it can fall back to a
#        'direct_translator' AI if configured.
#     4. This cycle repeats for a configured number of attempts.
#
#     Args:
#         human_query (str): The user's natural language query.
#         config_param (dict): The main application configuration object.
#         append_output_func (callable): A reference to UIManager.append_output for UI updates.
#         get_app_func (callable): A reference to UIManager.get_app_instance for UI invalidation.
#
#     Returns:
#         tuple[str | None, str | None]: A tuple containing (validated_command, raw_ai_response).
#                                        The command is None if no valid command could be produced.
#                                        The raw response is the last candidate from the AI.
#     """
#
# async def explain_linux_command_with_ai(command_to_explain: str, config_param: dict, append_output_func: callable) -> str | None:
#     """
#     Uses an AI model to provide a natural language explanation of a given command.
#
#     Args:
#         command_to_explain (str): The command string to be explained.
#         config_param (dict): The main application configuration object.
#         append_output_func (callable): A reference to UIManager.append_output for UI updates.
#
#     Returns:
#         str | None: The AI-generated explanation as a string, or a fallback message/None on error.
#     """
#
# **Key Global Constants/Variables:**
#   (None intended for direct external use)
#
# --- END API DOCUMENTATION ---

#!/usr/bin/env python

import asyncio
import re
import ollama # Assuming ollama is installed and accessible
import logging

# --- Logging Setup ---
# This logger will be specific to the ai_handler module
logger = logging.getLogger(__name__)

# --- AI Integration Constants ---
_COMMAND_PATTERN_STRING = (
    r"<bash>\s*'(.*?)'\s*</bash>|<bash>\s*(.*?)\s*</bash>|<bash>\s*`(.*?)`\s*</bash>|"
    r"```bash\s*\n([\s\S]*?)\n```|<code>\s*'(.*?)'\s*</code>|<code>\s*(.*?)\s*</code>|"
    r"<pre>\s*'(.*?)'\s*</pre>|<pre>\s*(.*?)\s*</pre>|<command>\s*'(.*?)'\s*</command>|"
    r"<command>\s*(.*?)\s*</command>|<cmd>\s*'(.*?)'\s*</cmd>|<cmd>\s*(.*?)\s*</cmd>|"
    r"```\s*([\s\S]*?)\s*```|<unsafe>\s*([\s\S]*?)\s*</unsafe>"
)
COMMAND_PATTERN = None
EXPECTED_GROUPS = 0
try:
    COMMAND_PATTERN = re.compile(_COMMAND_PATTERN_STRING, re.IGNORECASE | re.DOTALL)
    EXPECTED_GROUPS = _COMMAND_PATTERN_STRING.count('|') + 1
    logger.debug(f"COMMAND_PATTERN compiled with {COMMAND_PATTERN.groups} groups (expected {EXPECTED_GROUPS}).")
    if COMMAND_PATTERN.groups != EXPECTED_GROUPS:
        logger.error(f"CRITICAL: COMMAND_PATTERN groups mismatch: {COMMAND_PATTERN.groups} vs {EXPECTED_GROUPS}.")
        COMMAND_PATTERN = None
except re.error as e:
    logger.critical(f"Failed to compile COMMAND_PATTERN regex: {e}", exc_info=True)
    COMMAND_PATTERN = None
    EXPECTED_GROUPS = 0

_COMMAND_EXTRACT_GROUPS = list(range(1, EXPECTED_GROUPS)) if EXPECTED_GROUPS > 0 and COMMAND_PATTERN else []
_UNSAFE_TAG_CONTENT_GROUP = EXPECTED_GROUPS if EXPECTED_GROUPS > 0 and COMMAND_PATTERN else -1

_INNER_TAG_EXTRACT_PATTERN = re.compile(r"^\s*<([a-zA-Z0-9_:]+)(?:\s+[^>]*)?>([\s\S]*?)<\/\1>\s*$", re.DOTALL)

# --- AI Helper Functions ---

def _is_ai_refusal(text: str) -> bool:
    """
    Checks if a given text is likely an AI refusal to generate a command.
    """
    # NEW: Centralized refusal check.
    # This checks the beginning of the string for common refusal phrases.
    refusal_prefixes = ("sorry", "i cannot", "unable to", "cannot translate", "i am unable to")
    return text.lower().strip().startswith(refusal_prefixes)

def _clean_extracted_command(extracted_candidate: str) -> str:
    """Applies common cleaning steps to a potential command string."""
    processed_candidate = extracted_candidate.strip()
    original_for_log = processed_candidate

    inner_match = _INNER_TAG_EXTRACT_PATTERN.match(processed_candidate)
    if inner_match:
        tag_name = inner_match.group(1).lower()
        if tag_name in ["bash", "code", "cmd", "command", "pre"]:
            extracted_content = inner_match.group(2).strip()
            logger.debug(f"Stripped inner tag <{tag_name}>: '{original_for_log}' -> '{extracted_content}'")
            processed_candidate = extracted_content
        else:
            logger.debug(f"Inner tag <{tag_name}> found but not one of expected types to strip. Original: '{original_for_log}'")

    if len(processed_candidate) >= 2:
        if processed_candidate.startswith("'") and processed_candidate.endswith("'"):
            processed_candidate = processed_candidate[1:-1].strip()
            logger.debug(f"Stripped outer single quotes: '{original_for_log}' -> '{processed_candidate}'")
        elif processed_candidate.startswith("`") and processed_candidate.endswith("`"):
            processed_candidate = processed_candidate[1:-1].strip()
            logger.debug(f"Stripped outer backticks: '{original_for_log}' -> '{processed_candidate}'")

    if (processed_candidate.lower().startswith("bash ") or processed_candidate.lower().startswith("sh ")) and len(processed_candidate) > 6:
        prefix_len = 5 if processed_candidate.lower().startswith("bash ") else 3
        potential_inner_cmd = processed_candidate[prefix_len:].strip()
        if potential_inner_cmd.startswith("<") and potential_inner_cmd.endswith(">") and len(potential_inner_cmd) >=2:
            inner_cmd_content = potential_inner_cmd[1:-1].strip()
            if not any(c in inner_cmd_content for c in '<>|&;'):
                logger.debug(f"Stripped '{processed_candidate[:prefix_len]}<cmd>' pattern: '{original_for_log}' -> '{inner_cmd_content}'")
                processed_candidate = inner_cmd_content
            else:
                logger.debug(f"Retained '{processed_candidate[:prefix_len]}<cmd>' structure due to special chars: '{original_for_log}'")

    if len(processed_candidate) >= 2 and processed_candidate.startswith("<") and processed_candidate.endswith(">"):
        inner_content = processed_candidate[1:-1].strip()
        if not any(c in inner_content for c in '<>|&;'):
            logger.debug(f"Stripped general angle brackets: '{original_for_log}' -> '{inner_content}'")
            processed_candidate = inner_content
        else:
            logger.debug(f"Retained general angle brackets due to special chars: '{original_for_log}'")

    cleaned_linux_command = processed_candidate.strip()

    if cleaned_linux_command.startswith('/') and '/' not in cleaned_linux_command[1:]:
        cleaned_linux_command = cleaned_linux_command[1:]
        logger.debug(f"Stripped leading slash: '{original_for_log}' -> '{cleaned_linux_command}'")

    logger.debug(f"After cleaning: '{original_for_log}' -> '{cleaned_linux_command}'")

    # MODIFIED: The refusal check is now primarily handled at a higher level,
    # but we keep it here as a defense-in-depth for tagged content that might still contain a refusal.
    if _is_ai_refusal(cleaned_linux_command):
        logger.debug(f"Command discarded after cleaning (AI refusal): '{original_for_log}' -> '{cleaned_linux_command}'")
        return ""
    else:
        return cleaned_linux_command

async def is_valid_linux_command_according_to_ai(command_text: str, config_param: dict) -> bool | None:
    # ... (existing function is unchanged)
    if not command_text or len(command_text) < 2 or len(command_text) > 200:
        logger.debug(f"Skipping AI validation for command_text of length {len(command_text)}: '{command_text}'")
        return None

    validator_system_prompt = config_param['prompts']['validator']['system']
    validator_user_prompt = config_param['prompts']['validator']['user_template'].format(command_text=command_text)
    validator_model = config_param['ai_models']['validator']
    validator_attempts = config_param['behavior']['validator_ai_attempts']
    retry_delay = config_param['behavior']['ai_retry_delay_seconds'] / 2

    responses = []
    for i in range(validator_attempts):
        logger.info(f"To Validator AI (model: {validator_model}, attempt {i+1}/{validator_attempts}): '{command_text}'")
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=validator_model,
                messages=[
                    {'role': 'system', 'content': validator_system_prompt},
                    {'role': 'user', 'content': validator_user_prompt}
                ]
            )
            ai_answer = response['message']['content'].strip().lower()
            logger.debug(f"Validator AI response (attempt {i+1}) for '{command_text}': '{ai_answer}'")

            is_yes = re.search(r'\byes\b', ai_answer, re.IGNORECASE) is not None
            is_no = re.search(r'\bno\b', ai_answer, re.IGNORECASE) is not None

            if is_yes and not is_no:
                responses.append(True)
            elif is_no and not is_yes:
                responses.append(False)
            else:
                responses.append(None)
                logger.warning(f"Validator AI unclear answer (attempt {i+1}): '{ai_answer}'")
        except Exception as e:
            logger.error(f"Error calling Validator AI (attempt {i+1}) for '{command_text}': {e}", exc_info=True)
            responses.append(None)

        if i < validator_attempts - 1 and (len(responses) <= i+1 or responses[-1] is None):
            await asyncio.sleep(retry_delay)

    yes_count = responses.count(True)
    no_count = responses.count(False)
    logger.debug(f"Validator AI responses for '{command_text}': Yes: {yes_count}, No: {no_count}, Unclear/Error: {responses.count(None)}")

    if yes_count >= (validator_attempts // 2 + 1):
        return True
    elif no_count >= (validator_attempts // 2 + 1):
        return False
    else:
        logger.warning(f"Validator AI result inconclusive for '{command_text}' after {validator_attempts} attempts.")
        return None


async def _interpret_and_clean_tagged_ai_output(human_input: str, config_param: dict, append_output_func, get_app_func) -> tuple[str | None, str | None]:
    """Calls primary translation AI, parses, and cleans."""
    if COMMAND_PATTERN is None:
        logger.error("COMMAND_PATTERN regex not compiled. Cannot interpret AI output.")
        return None, None

    raw_candidate_from_regex = None
    ollama_model = config_param['ai_models']['primary_translator']
    system_prompt = config_param['prompts']['primary_translator']['system']
    user_prompt_template = config_param['prompts']['primary_translator']['user_template']
    retry_delay = config_param['behavior']['ai_retry_delay_seconds']
    ollama_call_retries = config_param.get('behavior', {}).get('ollama_api_call_retries', 2)
    last_exception_in_ollama_call = None

    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Primary AI (model: {ollama_model}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'")
            user_prompt = user_prompt_template.format(human_input=human_input)
            response = await asyncio.to_thread(
                ollama.chat,
                model=ollama_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]
            )
            ai_response = response['message']['content'].strip()
            logger.debug(f"Raw Primary AI response (attempt {attempt + 1}): {ai_response}")

            match = COMMAND_PATTERN.search(ai_response)
            if match:
                # This logic is mostly unchanged, but now focuses only on extraction
                if _UNSAFE_TAG_CONTENT_GROUP != -1 and COMMAND_PATTERN.groups >= _UNSAFE_TAG_CONTENT_GROUP and match.group(_UNSAFE_TAG_CONTENT_GROUP) is not None:
                    unsafe_message = match.group(_UNSAFE_TAG_CONTENT_GROUP).strip()
                    logger.warning(f"Primary AI indicated unsafe query: '{human_input}'. Message: '{unsafe_message}'")
                    append_output_func(f"⚠️ AI (Primary) Refusal: {unsafe_message}", style_class='ai-unsafe')
                    return None, ai_response

                for group_index in _COMMAND_EXTRACT_GROUPS:
                    if COMMAND_PATTERN.groups >= group_index and (extracted_candidate := match.group(group_index)) is not None:
                        if raw_candidate_from_regex is None:
                            raw_candidate_from_regex = extracted_candidate.strip()
                        cleaned_linux_command = _clean_extracted_command(extracted_candidate)
                        if cleaned_linux_command:
                            logger.debug(f"_interpret_and_clean_tagged_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_candidate_from_regex}'")
                            return cleaned_linux_command, raw_candidate_from_regex
                
                logger.warning(f"Primary AI matched pattern but no valid command extracted. Raw: {ai_response}, Match: '{match.group(0)}'")
            else:
                # MODIFICATION: If no pattern matches, check if the whole response is a refusal.
                if _is_ai_refusal(ai_response):
                    logger.warning(f"Primary AI refused query (no tags): '{human_input}'. Message: '{ai_response}'")
                    append_output_func(f"⚠️ AI (Primary) Refusal: {ai_response}", style_class='ai-unsafe')
                    # Return the refusal message as the raw candidate for context.
                    return None, ai_response
                else:
                    logger.error(f"Primary AI response did not match expected patterns. Response: {ai_response}")

            # This part is now only reached if a pattern matched but extraction failed,
            # or if it didn't match and wasn't a refusal. We should retry.
            if attempt < ollama_call_retries:
                logger.info(f"Retrying Primary AI call (parsing/match fail) (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(retry_delay)
                continue
            else:
                logger.error(f"Primary AI parsing/match failed after {ollama_call_retries+1} attempts. Last response: {ai_response}")
                return None, raw_candidate_from_regex if raw_candidate_from_regex is not None else ai_response

        except ollama.ResponseError as e_resp:
            current_attempt_exception = e_resp
            error_message = e_resp.error if hasattr(e_resp, 'error') else str(e_resp)
            append_output_func(f"❌ Ollama API Error (Primary): {error_message}", style_class='error')
            logger.error(f"Ollama API Error (Primary): {e_resp}", exc_info=True)
            if attempt == ollama_call_retries: return None, raw_candidate_from_regex
        except ollama.RequestError as e_req:
            current_attempt_exception = e_req
            append_output_func(f"❌ Ollama Connection Error (Primary): {e_req}", style_class='error')
            logger.error(f"Ollama Connection Error (Primary): {e_req}", exc_info=True)
            if attempt == ollama_call_retries: return None, raw_candidate_from_regex
        except Exception as e_gen:
            current_attempt_exception = e_gen
            append_output_func(f"❌ AI Processing Error (Primary): {e_gen}", style_class='error')
            logger.exception(f"Unexpected error in _interpret_and_clean_tagged_ai_output for '{human_input}'")
            if attempt == ollama_call_retries: return None, raw_candidate_from_regex
        
        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries:
                logger.info(f"Retrying Primary AI call after error '{type(current_attempt_exception).__name__}' (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(retry_delay)

    logger.error(f"_interpret_and_clean_tagged_ai_output exhausted retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}")
    return None, raw_candidate_from_regex

async def _get_direct_ai_output(human_input: str, config_param: dict, append_output_func, get_app_func) -> tuple[str | None, str | None]:
    # ... (existing function is unchanged, but could also benefit from the same refusal check)
    direct_translator_model = config_param['ai_models'].get('direct_translator')
    if not direct_translator_model:
        logger.info("_get_direct_ai_output skipped: No direct_translator_model configured.")
        return None, None

    system_prompt = config_param['prompts']['direct_translator']['system']
    user_prompt_template = config_param['prompts']['direct_translator']['user_template']
    retry_delay = config_param['behavior']['ai_retry_delay_seconds']
    ollama_call_retries = config_param.get('behavior', {}).get('ollama_api_call_retries', 2)
    raw_response_content = None
    last_exception_in_ollama_call = None

    for attempt in range(ollama_call_retries + 1):
        current_attempt_exception = None
        try:
            logger.info(f"To Direct AI (model: {direct_translator_model}, attempt {attempt + 1}/{ollama_call_retries+1}): '{human_input}'")
            user_prompt = user_prompt_template.format(human_input=human_input)
            response = await asyncio.to_thread(
                ollama.chat,
                model=direct_translator_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]
            )
            raw_response_content = response['message']['content'].strip()
            logger.debug(f"Raw Direct AI response (attempt {attempt + 1}): {raw_response_content}")

            cleaned_linux_command = _clean_extracted_command(raw_response_content)
            if cleaned_linux_command:
                logger.debug(f"_get_direct_ai_output returning: Cleaned='{cleaned_linux_command}', Raw='{raw_response_content}'")
                return cleaned_linux_command, raw_response_content
            else:
                # Also check for refusal here if cleaning results in an empty string
                if _is_ai_refusal(raw_response_content):
                     logger.warning(f"Direct AI refused query (after cleaning). Raw: {raw_response_content}")
                     return None, raw_response_content
                
                logger.warning(f"Direct AI response resulted in empty command after cleaning. Raw: {raw_response_content}")
                if attempt < ollama_call_retries:
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    return None, raw_response_content

        except ollama.ResponseError as e_resp:
            current_attempt_exception = e_resp
            error_message = e_resp.error if hasattr(e_resp, 'error') else str(e_resp)
            append_output_func(f"❌ Ollama API Error (Direct): {error_message}", style_class='error')
            logger.error(f"Ollama API Error (Direct): {e_resp}", exc_info=True)
            if attempt == ollama_call_retries: return None, raw_response_content
        except ollama.RequestError as e_req:
            current_attempt_exception = e_req
            append_output_func(f"❌ Ollama Connection Error (Direct): {e_req}", style_class='error')
            logger.error(f"Ollama Connection Error (Direct): {e_req}", exc_info=True)
            if attempt == ollama_call_retries: return None, raw_response_content
        except Exception as e_gen:
            current_attempt_exception = e_gen
            append_output_func(f"❌ AI Processing Error (Direct): {e_gen}", style_class='error')
            logger.exception(f"Unexpected error in _get_direct_ai_output for '{human_input}'")
            if attempt == ollama_call_retries: return None, raw_response_content
        
        if current_attempt_exception:
            last_exception_in_ollama_call = current_attempt_exception
            if attempt < ollama_call_retries:
                logger.info(f"Retrying Direct AI call after error '{type(current_attempt_exception).__name__}' (attempt {attempt + 2}/{ollama_call_retries+1}) for '{human_input}'.")
                await asyncio.sleep(retry_delay)

    logger.error(f"_get_direct_ai_output exhausted retries for '{human_input}'. Last exception: {last_exception_in_ollama_call}")
    return None, raw_response_content

# The rest of the file (get_validated_ai_command, explain_linux_command_with_ai) remains unchanged.
async def get_validated_ai_command(human_query: str, config_param: dict, append_output_func, get_app_func) -> tuple[str | None, str | None]:
    # ... (existing function is unchanged)
    logger.info(f"Attempting validated translation for: '{human_query}'")
    last_raw_candidate_primary = None
    last_raw_candidate_secondary = None
    last_cleaned_command_attempt = None

    translation_cycles = config_param['behavior']['translation_validation_cycles']
    retry_delay = config_param['behavior']['ai_retry_delay_seconds']
    primary_model_name = config_param['ai_models']['primary_translator']
    secondary_model_name = config_param['ai_models'].get('direct_translator')

    for i in range(translation_cycles):
        append_output_func(f"🧠 AI translation & validation cycle {i+1}/{translation_cycles} for: '{human_query}'", style_class='ai-thinking')
        if get_app_func().is_running : get_app_func().invalidate()

        append_output_func(f"     P-> Trying Primary Translator ({primary_model_name})...", style_class='ai-thinking-detail')
        logger.debug(f"Cycle {i+1}: Trying primary translator.")
        cleaned_command_p, raw_candidate_p = await _interpret_and_clean_tagged_ai_output(human_query, config_param, append_output_func, get_app_func)
        if raw_candidate_p is not None: last_raw_candidate_primary = raw_candidate_p

        if cleaned_command_p:
            last_cleaned_command_attempt = cleaned_command_p
            append_output_func(f"  P-> Primary Translated to: '{cleaned_command_p}'. Validating...", style_class='ai-thinking-detail')
            if get_app_func().is_running : get_app_func().invalidate()
            is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_p, config_param)
            if is_valid_by_validator is True:
                logger.info(f"Validator confirmed primary: '{cleaned_command_p}'")
                append_output_func(f"  P-> ✅ AI Validator confirmed: '{cleaned_command_p}'", style_class='success')
                return cleaned_command_p, raw_candidate_p
            elif is_valid_by_validator is False:
                logger.warning(f"Validator rejected primary: '{cleaned_command_p}'")
                append_output_func(f"  P-> ❌ AI Validator rejected: '{cleaned_command_p}'.", style_class='warning')
            else:
                logger.warning(f"Validator inconclusive for primary: '{cleaned_command_p}'")
                append_output_func(f"  P-> ⚠️ AI Validator inconclusive for: '{cleaned_command_p}'.", style_class='warning')
        else:
            logger.warning(f"Primary AI translation (cycle {i+1}) failed. Raw candidate: {raw_candidate_p}")
            append_output_func(f"  P-> Primary translation failed.", style_class='warning')

        if secondary_model_name:
            append_output_func(f"     S-> Trying Secondary Translator ({secondary_model_name})...", style_class='ai-thinking-detail')
            logger.debug(f"Cycle {i+1}: Trying secondary translator.")
            cleaned_command_s, raw_candidate_s = await _get_direct_ai_output(human_query, config_param, append_output_func, get_app_func)
            if raw_candidate_s is not None: last_raw_candidate_secondary = raw_candidate_s

            if cleaned_command_s:
                last_cleaned_command_attempt = cleaned_command_s
                append_output_func(f"  S-> Secondary Translated to: '{cleaned_command_s}'. Validating...", style_class='ai-thinking-detail')
                if get_app_func().is_running : get_app_func().invalidate()
                is_valid_by_validator = await is_valid_linux_command_according_to_ai(cleaned_command_s, config_param)
                if is_valid_by_validator is True:
                    logger.info(f"Validator confirmed secondary: '{cleaned_command_s}'")
                    append_output_func(f"  S-> ✅ AI Validator confirmed: '{cleaned_command_s}'", style_class='success')
                    return cleaned_command_s, raw_candidate_s
                elif is_valid_by_validator is False:
                    logger.warning(f"Validator rejected secondary: '{cleaned_command_s}'")
                    append_output_func(f"  S-> ❌ AI Validator rejected: '{cleaned_command_s}'.", style_class='warning')
                else:
                    logger.warning(f"Validator inconclusive for secondary: '{cleaned_command_s}'")
                    append_output_func(f"  S-> ⚠️ AI Validator inconclusive for: '{cleaned_command_s}'.", style_class='warning')
            else:
                logger.warning(f"Secondary AI translation (cycle {i+1}) failed. Raw candidate: {raw_candidate_s}")
                append_output_func(f"  S-> Secondary translation failed.", style_class='warning')
        else:
            logger.debug(f"Cycle {i+1}: Secondary translator not configured or not used this cycle.")

        if i < translation_cycles - 1:
            append_output_func(f"Retrying translation & validation cycle {i+2}/{translation_cycles}...", style_class='ai-thinking')
            await asyncio.sleep(retry_delay)
        else:
            logger.error(f"All {translation_cycles} translation cycles failed for '{human_query}'.")
            append_output_func(f"❌ AI failed to produce validated command after {translation_cycles} cycles.", style_class='error')
            final_raw_candidate = last_raw_candidate_secondary if last_raw_candidate_secondary is not None else last_raw_candidate_primary
            if last_cleaned_command_attempt:
                append_output_func(f"ℹ️ Offering last unvalidated attempt for categorization: '{last_cleaned_command_attempt}'", style_class='info')
            return last_cleaned_command_attempt, final_raw_candidate

    return None, None

async def explain_linux_command_with_ai(command_to_explain: str, config_param: dict, append_output_func) -> str | None:
    # ... (existing function is unchanged)
    logger.info(f"Requesting AI explanation for command: '{command_to_explain}'")
    if not command_to_explain:
        return "Cannot explain an empty command."

    explainer_model = config_param.get('ai_models', {}).get('explainer')
    explainer_prompts = config_param.get('prompts', {}).get('explainer')

    if not explainer_model or not explainer_prompts:
        logger.error("Explainer AI model or prompts not configured.")
        append_output_func("❌ AI Explainer model/prompts not configured.", style_class='error')
        return None

    system_prompt = explainer_prompts['system']
    user_prompt = explainer_prompts['user_template'].format(command_text=command_to_explain)
    
    retry_delay = config_param.get('behavior', {}).get('ai_retry_delay_seconds', 1)
    ollama_call_retries = config_param.get('behavior', {}).get('ollama_api_call_retries', 2)

    for attempt in range(ollama_call_retries + 1):
        try:
            logger.info(f"To Explainer AI (model: {explainer_model}, attempt {attempt + 1}/{ollama_call_retries + 1}): '{command_to_explain}'")
            response = await asyncio.to_thread(
                ollama.chat,
                model=explainer_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ]
            )
            explanation = response['message']['content'].strip()
            logger.debug(f"Explainer AI response: {explanation}")
            if explanation:
                return explanation
            else:
                logger.warning(f"Explainer AI returned an empty response for '{command_to_explain}'.")
                if attempt == ollama_call_retries:
                    return "AI Explainer returned an empty response."
        except ollama.ResponseError as e_resp:
            error_message = e_resp.error if hasattr(e_resp, 'error') else str(e_resp)
            append_output_func(f"❌ Ollama API Error (Explainer): {error_message}", style_class='error')
            logger.error(f"Ollama API Error (Explainer): {e_resp}", exc_info=True)
            if attempt == ollama_call_retries: return f"Ollama API error during explanation: {error_message}"
        except ollama.RequestError as e_req:
            append_output_func(f"❌ Ollama Connection Error (Explainer): {e_req}", style_class='error')
            logger.error(f"Ollama Connection Error (Explainer): {e_req}", exc_info=True)
            if attempt == ollama_call_retries: return f"Ollama connection error during explanation: {e_req}"
        except Exception as e:
            logger.error(f"Unexpected error calling Explainer AI for '{command_to_explain}': {e}", exc_info=True)
            append_output_func(f"❌ Unexpected error during AI explanation: {e}", style_class='error')
            if attempt == ollama_call_retries: return f"Unexpected error during AI explanation: {e}"
        
        if attempt < ollama_call_retries:
            logger.info(f"Retrying Explainer AI call (attempt {attempt + 2}/{ollama_call_retries + 1}) for '{command_to_explain}'.")
            await asyncio.sleep(retry_delay)

    return "AI explanation failed after multiple retries."
#!/usr/bin/env python3
"""
Shared VMware vSphere task waiting utilities.
"""

import logging
import time

logger = logging.getLogger(__name__)


def wait_for_task(task, timeout=None):
    """
    Wait for a vCenter task to complete.

    Args:
        task: pyVmomi Task object
        timeout: Maximum seconds to wait (None = no timeout)

    Returns:
        True if task completed successfully, False otherwise
    """
    try:
        start_time = time.time()

        while task.info.state in ['running', 'queued']:
            if timeout is not None and (time.time() - start_time) > timeout:
                logger.warning(f"Task timeout after {timeout}s in state '{task.info.state}'")
                return False
            time.sleep(1)

        if task.info.state == 'success':
            return True

        logger.error(f"Task failed: {task.info.error}")
        return False

    except Exception as e:
        logger.error(f"Error waiting for task: {e}")
        return False


def wait_for_task_with_questions(task, vm, timeout=None):
    """
    Wait for a vCenter task to complete, handling runtime questions when needed.

    Used for CD eject operations that may prompt for confirmation.

    Args:
        task: pyVmomi Task object
        vm: VM object to check for runtime questions
        timeout: Maximum seconds to wait (None = no timeout)

    Returns:
        True if task completed successfully, False otherwise
    """
    try:
        start_time = time.time()

        while task.info.state in ['running', 'queued']:
            if vm.runtime.question:
                question = vm.runtime.question
                question_text = question.text if hasattr(question, 'text') else str(question)
                logger.info(f"🤖 VM runtime question detected: {question_text}")

                if any(keyword in question_text.lower() for keyword in ('cd', 'cdrom', 'dvd')):
                    logger.info("✅ Answering CD ejection question for VM")
                    try:
                        if (
                            hasattr(question, 'choice')
                            and hasattr(question.choice, 'choiceInfo')
                            and question.choice.choiceInfo
                        ):
                            answer = question.choice.choiceInfo[0].key
                            vm.AnswerVM(question.id, answer)
                            logger.info(f"✅ Answered CD ejection question with key: {answer}")
                        else:
                            logger.warning("No choices available in runtime question")
                    except Exception as e:
                        logger.warning(f"Could not answer runtime question: {e}")

            if timeout is not None and (time.time() - start_time) > timeout:
                logger.warning(f"Task timeout after {timeout}s in state '{task.info.state}'")
                return False
            time.sleep(1)

        if task.info.state == 'success':
            return True

        logger.error(f"Task failed: {task.info.error}")
        return False

    except Exception as e:
        logger.error(f"Error waiting for task with questions: {e}")
        return False

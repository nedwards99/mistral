import json
import logging
import math
import os

from experiment_impact_tracker.data_interface import DataInterface
from transformers import PreTrainedModel, TrainerControl, TrainerState, TrainingArguments
from transformers.integrations import WandbCallback


logger = logging.getLogger(__name__)


def compute_metrics(preds):
    """
    Compute custom metrics using the predictions and labels from the LM.
    """
    _ = preds.predictions, preds.label_ids
    return {"my_metric": 0.0}


class CustomWandbCallback(WandbCallback):
    """
    Custom Weights and Biases Callback used by Mistral for logging information from the Huggingface Trainer.

    # TODO: Override the methods below to log useful things
    """

    def __init__(self, project: str, energy_log: str, json_file: str):

        super(CustomWandbCallback, self).__init__()

        # Set the project name
        if isinstance(project, str):
            logger.info(f"Setting wandb project: {project}")
            os.environ["WANDB_PROJECT"] = project

        # Set wandb.watch(model) to False, throws an error otherwise
        # Note: we manually watch the model in self.on_train_begin(..)
        os.environ["WANDB_WATCH"] = "false"

        self.energy_log = energy_log

        # Set up json schema
        self.json_file = json_file

        self.json_schema = {
            "model_info": {},
            "energy_metrics": [],
            "global_step_info": [],
        }

        self.write_to_json(self.json_schema, self.json_file)

    def write_to_json(self, data, file_name):
        with open(file_name, "w") as f:
            json.dump(data, f)

    def on_init_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_init_end(args, state, control, **kwargs)

    def on_epoch_begin(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_epoch_begin(args, state, control, **kwargs)

    def on_epoch_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_epoch_end(args, state, control, **kwargs)

        # Log energy information @ epoch
        energy_data = DataInterface(args.energy_dir)
        energy_metrics = {
            "carbon_kg": energy_data.kg_carbon,
            "total_power": energy_data.total_power,
            "power_usage_effectiveness": energy_data.PUE,
            "exp_len_hrs": energy_data.exp_len_hours,
        }
        self._wandb.log(
            {"energy_metrics": energy_metrics},
            step=state.epoch,
        )

        try:
            # Log energy information @ epoch
            energy_data = DataInterface(self.energy_log)
            energy_metrics = {
                "carbon_kg": energy_data.kg_carbon,
                "total_power": energy_data.total_power,
                "power_usage_effectiveness": energy_data.PUE,
                "exp_len_hrs": energy_data.exp_len_hours,
            }
            self._wandb.log(
                {"energy_metrics": energy_metrics},
                step=state.global_step,
            )

            self.json_schema["energy_metrics"].append(energy_metrics)
            self.write_to_json(self.json_schema, self.json_file)
        except ValueError:
            # In case the energy tracker raises "Unable to get either GPU or CPU metric."
            pass

    def on_step_begin(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_step_begin(args, state, control, **kwargs)

    def on_step_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        # Log step information
        self._wandb.log(
            {
                "info/global_step": state.global_step,
            },
            step=state.global_step,
        )

        self.json_schema["global_step_info"].append(state.global_step)
        self.write_to_json(self.json_schema, self.json_file)

    def on_evaluate(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        metrics=None,
        **kwargs,
    ):
        super().on_evaluate(args, state, control, metrics=metrics, **kwargs)

    def on_save(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_save(args, state, control, **kwargs)

    def on_prediction_step(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_prediction_step(args, state, control, **kwargs)

    def on_train_begin(
        self,
        args,
        state,
        control,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_train_begin(args, state, control, model, **kwargs)
        # Watch the model
        self._wandb.watch(model)

        # Log model information
        self._wandb.log(
            {
                "model-info/num_parameters": model.num_parameters(),
                "model-info/trainable_parameters": model.num_parameters(only_trainable=True),
            },
            step=state.global_step,
        )

        self.json_schema["model_info"] = {
            "num_parameters": model.num_parameters(),
            "trainable_parameters": model.num_parameters(only_trainable=True),
        }
        self.write_to_json(self.json_schema, self.json_file)

    def on_train_end(
        self,
        args,
        state,
        control,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        **kwargs,
    ):
        super().on_train_end(args, state, control, model, tokenizer, **kwargs)

    def on_log(
        self,
        args,
        state,
        control,
        model: PreTrainedModel = None,
        tokenizer=None,
        optimizer=None,
        lr_scheduler=None,
        train_dataloader=None,
        eval_dataloader=None,
        logs=None,
        **kwargs,
    ):
        # Log train perplexity
        if any([k == "loss" for k in logs]):
            logs["perplexity"] = math.exp(logs["loss"])
        super().on_log(args, state, control, model, logs, **kwargs)

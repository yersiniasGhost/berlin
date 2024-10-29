import pandas as pd
import json
from pathlib import Path
from typing import List, Tuple
import numpy as np

from GeneticOptimizer.obm_optimizer.json_parser.payload_parser import InspectionOptimizer
from GeneticOptimizer.obm_optimizer.obm_individual import OBMIndividual


def read_task_spreadsheet(task_csv: Path) -> Tuple[pd.DataFrame, List[str]]:
    if not task_csv.exists():
        raise Exception(f"WTF!  File doesn't exist:  {task_csv}")
    df = pd.read_csv(task_csv)
    unique_asset_names = list(df["Asset_Client_ID"].unique())
    return df, unique_asset_names


# Given the path to a Newton payload.  Read the files and get information about the Assets
def create_asset_mapping(asset_path: Path, asset_list: List[str]) -> dict:
    mapping = {}
    for file in asset_path.glob('*.json'):
        if file.name[0:5] == "asset":
            file_path = asset_path / file.name
            with file_path.open() as asset_data:
                print(file_path)
                asset_json = json.load(asset_data)
                for item in asset_json:
                    if "__Asset__" in item.keys():
                        asset = item['__Asset__']
                        if asset['name'] in asset_list:
                            mapping[asset['name']] = (asset["id"], file_path)
    return mapping


#  From the Newton payload, get the component IDs
def get_component_map(asset_name: str, asset_mapping: dict) -> dict:
    asset_file = asset_mapping[asset_name][1]
    mapper = {}
    with asset_file.open() as asset_data:
        asset_json = json.load(asset_data)
        for item in asset_json:
            if "__Component__" in item.keys():
                mapper[item["__Component__"]['name']] = item["__Component__"]['id']
    return mapper


def get_component_pof(bcr_solution_path: Path, asset_id: str, component_id: str):
    bcr_input = bcr_solution_path / f'so_{asset_id}.json'
    if bcr_input.exists():
        with bcr_input.open() as data_file:
            data = json.load(data_file)

        for cc in data['components']:
            if cc['componentId'] == component_id:
                candidate = cc['candidates'][0]
                return candidate['reliability']
        raise Exception(f"Didn't find component in BCR Solution: {component_id} in {bcr_input}")
    else:
        print("Cannot locate: ", bcr_input)


def create_stage2_payload(task_dataframe: pd.DataFrame, asset_name: str,
                          asset_mapping: dict, output_path: Path, bcr_solution_path: Path):
    asset_df = task_dataframe[task_dataframe["Asset_Client_ID"] == asset_name]
    component_map = get_component_map(asset_name, asset_mapping)
    components = task_dataframe[task_dataframe["Asset_Client_ID"] == asset_name]['Component_Client_ID'].unique()
    for component_name in components:
        component_df = asset_df[asset_df['Component_Client_ID'] == component_name]
        component_tasks = []
        for _, row in component_df.iterrows():
            data = {"minimum_task_separation": row["Min Task Separation (Days)"],
                    "maximum_task_separation": row["Max Task Separation (Days)"],
                    "cost": row[" TotalCostDollars "],
                    "name": row["Task_Definition"],
                    "effectiveness": row["Quantitative Inspection Effectiveness"]}
            component_tasks.append(data)
            eta = row['eta']
            beta = row['beta']
        detection = {"function": "weibull",
                     "parameters": {"eta": eta, "beta": beta}
                     }
        component_id = component_map[component_name]
        reliability = get_component_pof(bcr_solution_path, asset_mapping[asset_name][0], component_id)
        payload = {
            "asset_name": asset_name,
            "asset_id": asset_mapping[asset_name][0],
            "component_name": component_name,
            "component_id": component_id,
            "test_name": component_name,
            "stalled_counter": 200,
            "detection": detection,
            "tasks": component_tasks,
            "PoF": {
                "function": "reliability",
                "data": reliability
            }
        }
        component_name = component_name.replace('/', '-')
        component_name = component_name.replace(' ', '-')
        output_file = output_path / f"{component_name}-{component_id}.json"
        print(output_file)
        with output_file.open('w') as payload_out:
            payload_out.write(json.dumps(payload, indent=4))


def output_task_spreadsheet(optimizer: InspectionOptimizer, individual: OBMIndividual, output_path: Path,
                            output: str, start_date: np.datetime64):
    task_dates = individual.get_task_dates()
    task_list = list(optimizer.task_dict.values())

    asset_client_id, component_client_id, task_crs_id = [], [], []
    task_name, schedule_date, status, bcr = [], [], [], []
    for t, task in enumerate(task_list):
        for d in task_dates[t]:
            asset_client_id.append(optimizer.asset_client_id)
            component_client_id.append(optimizer.component_client_id)
            task_crs_id.append("")
            task_name.append(task.name)
            schedule_date.append(str(start_date + d))
            status.append("PLANNED")
            bcr.append("0")
    df = pd.DataFrame({'Asset Client ID': asset_client_id,
                       'Component Client ID': component_client_id,
                       'Task CRS ID': task_crs_id,
                       'Task': task_name,
                       'Scheduled Date': schedule_date,
                       'Implementation Status': status,
                       'TO Benefit Cost Ratio': bcr
                       })
    cvs_file = output_path / f"{output}.csv"
    df.to_csv(cvs_file, index=False)


if __name__ == "__main__":
    # input_file = Path("/home/frich/Downloads/Tasks for GA - Rev1.csv")
    # bcr_solutions = Path("/home/frich/tmp/bcr_solutions/1018")
    # newton_payload = Path("/home/frich/devel/PINNACLE/Mount%20Hood/tests/regression_tests/data/task_optimizer_payloads/valero-20210920-std/")
    # output_path = Path("/home/frich/tmp/v3r_optimizer/1018")

    input_file = Path("/home/toadministrator/V3R/210920/qie_ga/TasksforGARev1-v3r.csv")
    bcr_solutions = Path("/home/toadministrator/V3R/210920/bcr_solution/1025/lowhse_output")
    newton_payload = Path("/home/toadministrator/V3R/210920/payloads/valero-lowhse-210920")
    prj_output_path = Path("/home/toadministrator/V3R/210920/qie_ga/1025")

    prj_output_path.mkdir(exist_ok=True, parents=True)
    df2, assets = read_task_spreadsheet(input_file)
    asset_mapper = create_asset_mapping(newton_payload, assets)

    for the_asset in assets:
        create_stage2_payload(df2, the_asset, asset_mapper, prj_output_path, bcr_solutions)

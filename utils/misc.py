def transform_groups(groups):
    final_groups = []
    # groups = [g for _, g in groups.items()]
    for group in groups:
        if group.get("subgroup") is not None:
            for subgroup in group.get("subgroup"):
                subgroup["order"] = group.get("order")
                final_groups.append(subgroup)
        else:
            final_groups.append(group)

    return final_groups

def format_number(number):
    return f"{number:,}"
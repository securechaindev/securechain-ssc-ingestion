class PyPIConstraintsParser:
    def __init__(self):
        pass

    async def parse(self, constraints: str) -> str:
        if constraints:
            ctcs = [
                f"!= {ctc.split(' ')[-1]}" if "||" in ctc else ctc.strip()
                for ctc in constraints.split(",")
            ]
            if ctcs:
                clean_ctcs = await self.clean(ctcs)
                if clean_ctcs:
                    return clean_ctcs
        return "any"


    async def clean(self, raw_constraints: list[str]) -> str:
        constraints = []
        for raw_constraint in raw_constraints:
            try:
                if " " not in raw_constraint:
                    if raw_constraint.isalpha():
                        continue
                    for index, char in enumerate(raw_constraint):
                        if char.isdigit():
                            raw_constraint = (
                                raw_constraint[:index] + " " + raw_constraint[index:]
                            )
                            break
                pos = ""
                for index, char in enumerate(raw_constraint):
                    if char.isdigit():
                        pos = index
                        break
                if isinstance(pos, str):
                    return "any"
                operator = raw_constraint[:pos].strip()
                version = raw_constraint[pos:].strip()
                if "==" in operator and "*" in version:
                    pos = version.find("*")
                    version = version[: pos - 1]
                    constraints.append(">=" + version)
                    constraints.append(
                        "<" + version[: pos - 2] + str(int(version[pos - 2]) + 1)
                    )
                elif "=" in operator and all(
                    symbol not in operator for symbol in ("<", ">", "~", "!")
                ):
                    constraints.append("==" + version)
                elif "!=" in operator and "*" in version:
                    pos = version.find("*")
                    version = version[: pos - 1]
                    constraints.append("<" + version)
                    constraints.append(
                        ">=" + version[: pos - 2] + str(int(version[pos - 2]) + 1)
                    )
                elif any(symbol in operator for symbol in ("~=", "~>")):
                    parts = version.split(".")
                    have_exc = False
                    if "!" in parts[0]:
                        have_exc = True
                        new_parts = parts[0].split("!")
                        for item in reversed(new_parts):
                            parts.insert(0, item)
                    cleaned_parts = []
                    for index, part in enumerate(parts):
                        if part.isdigit() or index == 0:
                            cleaned_parts.append(part)
                    if have_exc:
                        version =  cleaned_parts[0] + "!" + ".".join(cleaned_parts[1:])
                    else:
                        version =  ".".join(cleaned_parts)
                    cleaned_parts[-2] = str(int(cleaned_parts[-2]) + 1)
                    cleaned_parts.pop()
                    if have_exc:
                        constraints.append(">=" + version)
                        constraints.append("<" + cleaned_parts[0] + "!" + ".".join(cleaned_parts[1:]))
                    else:
                        constraints.append(">=" + version)
                        constraints.append("<" + ".".join(cleaned_parts))
                else:
                    constraints.append(f"{operator} {version}")
            except Exception:
                return "any"
        return ", ".join(constraints)

    async def get_first_position(self, data: str, operators: list[str]) -> int:
        if not any(operator in data for operator in operators):
            return len(data)
        for index, char in enumerate(data):
            if char in operators:
                return index
        return 0

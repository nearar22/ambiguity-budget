import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const contract = process.env.CONTRACT_ADDRESS?.trim();
const raw = process.env.GENLAYER_PRIVATE_KEY?.trim();
const instruction = process.env.DEMO_INSTRUCTION_URL?.trim();
const constraint = process.env.DEMO_CONSTRAINT_URL?.trim();
if (!contract || !raw || !instruction || !constraint) throw new Error("Contract, key, instruction URL, and constraint URL are required");
const key = raw.startsWith("0x") ? raw : `0x${raw}`;
const chain = { ...studioDevnet, id: 61997, name: "GenLayer Studio Next", rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } } };
const client = createClient({ chain, account: createAccount(key) });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const id = `ambiguity-demo-${Date.now().toString(36)}`;
async function finalized(hash) {
  for (let i = 0; i < 300; i++) {
    const receipt = await client.getTransaction({ hash }).catch(() => null);
    const status = String(receipt?.statusName ?? receipt?.status ?? "PENDING").toUpperCase();
    if (status === "FINALIZED") return receipt;
    if (["UNDETERMINED", "DECLINED", "CANCELED", "CANCELLED"].includes(status)) throw new Error(`Transaction ended ${status}`);
    await sleep(3000);
  }
  throw new Error("Transaction timed out");
}
async function write(label, functionName, args, intelligent = false) {
  const fees = await client.estimateTransactionFees({ leaderTimeunitsAllocation: intelligent ? 500n : 180n, validatorTimeunitsAllocation: intelligent ? 600n : 360n });
  const hash = await client.writeContract({ address: contract, functionName, args, fees });
  console.log(`${label}_TX=${hash}`);
  const receipt = await finalized(hash);
  if (String(receipt.statusName ?? receipt.status).toUpperCase() !== "FINALIZED" || String(receipt.txExecutionResultName ?? receipt.txExecutionResult) !== "FINISHED_WITH_RETURN") throw new Error(`${label} failed`);
}
await write("CREATE", "create_assessment", [id, "Export cleanup execution gate", "Determine whether an agent can execute the cleanup instruction without guessing its destructive scope.", instruction, constraint]);
await write("ANALYZE", "analyze", [id], true);
await write("FINALIZE", "finalize", [id]);
const state = await client.readContract({ address: contract, functionName: "get_assessment", args: [id], jsonSafeReturn: true });
console.log(`DEMO_ASSESSMENT=${id}\nSTATE=${state.status}\nOUTCOME=${state.analysis?.outcome}\nREADINGS=${state.analysis?.readings?.length}`);
if (state.status !== "FINAL" || state.analysis?.receipts?.length !== 2) throw new Error("Live smoke state is incomplete");

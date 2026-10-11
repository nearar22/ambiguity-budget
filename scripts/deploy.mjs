import { readFileSync } from "node:fs";
import { createAccount, createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";

const raw = process.env.GENLAYER_PRIVATE_KEY?.trim();
if (!raw) throw new Error("GENLAYER_PRIVATE_KEY is required");
const key = raw.startsWith("0x") ? raw : `0x${raw}`;
const chain = { ...studioDevnet, id: 61997, name: "GenLayer Studio Next", rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } } };
const client = createClient({ chain, account: createAccount(key) });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function finalized(hash) {
  for (let i = 0; i < 240; i++) {
    const receipt = await client.getTransaction({ hash }).catch(() => null);
    const status = String(receipt?.statusName ?? receipt?.status ?? "PENDING").toUpperCase();
    if (status === "FINALIZED") return receipt;
    if (["UNDETERMINED", "DECLINED", "CANCELED", "CANCELLED"].includes(status)) throw new Error(`Deployment ended ${status}`);
    await sleep(3000);
  }
  throw new Error("Deployment timed out");
}
const code = new Uint8Array(readFileSync(new URL("../contracts/ambiguity_budget.py", import.meta.url)));
const fees = await client.estimateTransactionFees({ leaderTimeunitsAllocation: 250n, validatorTimeunitsAllocation: 500n });
const hash = await client.deployContract({ code, args: [], fees });
console.log(`DEPLOY_TX=${hash}`);
const receipt = await finalized(hash);
const status = String(receipt.statusName ?? receipt.status ?? "unknown");
const execution = String(receipt.txExecutionResultName ?? receipt.txExecutionResult ?? "unknown");
const consensus = String(receipt.resultName ?? receipt.result_name ?? "unknown");
if (status !== "FINALIZED" || execution !== "FINISHED_WITH_RETURN" || consensus === "MAJORITY_DISAGREE") throw new Error("Deployment failed");
const address = receipt?.data?.contract_address ?? receipt?.txDataDecoded?.contractAddress;
if (!address) throw new Error("Missing contract address");
console.log(`CONTRACT_ADDRESS=${address}`);

/**
 * Pay the machine wallet on agung (e.g. per sample_found).
 * Env: same Dynamic vars as fund.mjs, plus MACHINE_ADDRESS, PAY_AMOUNT, optional PAY_REFERENCE.
 */
import { DynamicEvmWalletClient } from "@dynamic-labs-wallet/node-evm";
import { parseEther } from "viem";

const AGUNG_CHAIN_ID = 9990;
const RPC =
  process.env.PEAQOS_RPC_URL ||
  process.env.AGUNG_RPC ||
  "https://peaq-agung.api.onfinality.io/public";

function need(name) {
  const v = process.env[name];
  if (!v) {
    console.log("[dynamic] pay skipped, missing", name);
    process.exit(0);
  }
  return v;
}

const amount = process.env.PAY_AMOUNT || process.env.DISCOVERY_PAY_AMOUNT || "";
if (!amount || Number(amount) <= 0) {
  console.log("[dynamic] pay skipped, PAY_AMOUNT not set or zero");
  process.exit(0);
}

const authToken = need("DYNAMIC_AUTH_TOKEN");
const environmentId = need("DYNAMIC_ENVIRONMENT_ID");
const accountAddress =
  process.env.PAYER_DYNAMIC_ACCOUNT_ADDRESS || process.env.DYNAMIC_ACCOUNT_ADDRESS;
if (!accountAddress) {
  console.log("[dynamic] pay skipped, missing PAYER_DYNAMIC_ACCOUNT_ADDRESS");
  process.exit(0);
}
const machine = need("MACHINE_ADDRESS");
const reference = process.env.PAY_REFERENCE || "discovery";

const client = new DynamicEvmWalletClient({ environmentId });
await client.authenticateApiToken(authToken);

const clientArgs = {
  accountAddress,
  chainId: AGUNG_CHAIN_ID,
  rpcUrl: RPC,
};
if (process.env.DYNAMIC_WALLET_PASSWORD) {
  clientArgs.password = process.env.DYNAMIC_WALLET_PASSWORD;
}
const walletClient = await client.getWalletClient(clientArgs);

try {
  const hash = await walletClient.sendTransaction({
    to: machine,
    value: parseEther(amount),
  });
  console.log(
    "[dynamic] paid_escrow_release",
    reference,
    "from",
    accountAddress,
    "to",
    machine,
    "amount",
    amount,
    "tx",
    hash,
  );
} catch (err) {
  console.error("[dynamic] pay failed", reference, err?.message || err);
  process.exit(1);
}

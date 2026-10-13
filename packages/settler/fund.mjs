/**
 * Earth-side owner wallet on agung (chain 9990) funds the machine address.
 * Dynamic server wallets: getWalletClient({ chainId, rpcUrl }).
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
    console.log("[dynamic] skipped, missing", name);
    process.exit(0);
  }
  return v;
}

const authToken = need("DYNAMIC_AUTH_TOKEN");
const environmentId = need("DYNAMIC_ENVIRONMENT_ID");
const accountAddress = need("DYNAMIC_ACCOUNT_ADDRESS");
const machine = need("MACHINE_ADDRESS");
const amount = process.env.DYNAMIC_FUND_AMOUNT || "0.05";

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

const hash = await walletClient.sendTransaction({
  to: machine,
  value: parseEther(amount),
});
console.log("[dynamic] funded", machine, "amount", amount, "tx", hash);

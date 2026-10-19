package demo;

import java.util.LinkedHashMap;
import java.util.Map;

/** Tiny class under test for the demo project (10% discount when more than 3 items). */
public class ShoppingCart {
    private final Map<String, Item> items = new LinkedHashMap<>();
    private final Map<String, Integer> qty = new LinkedHashMap<>();
    private String coupon, shipping, receipt;
    private boolean synced;

    public void add(Item item, int n) {
        items.put(item.getName(), item);
        qty.merge(item.getName(), n, Integer::sum);
    }
    public void remove(String name) { items.remove(name); qty.remove(name); }
    public int itemCount() { return qty.values().stream().mapToInt(Integer::intValue).sum(); }
    public boolean hasItem(String name) { return items.containsKey(name); }
    public int total() {
        int sum = 0;
        for (Map.Entry<String, Item> e : items.entrySet()) sum += e.getValue().getPrice() * qty.get(e.getKey());
        return itemCount() > 3 ? sum * 9 / 10 : sum;
    }
    public void applyCoupon(String code) { coupon = code; }
    public void setShipping(String mode) { shipping = mode; }
    public void checkout() { receipt = "total=" + total() + ";coupon=" + coupon + ";shipping=" + shipping; }
    public String receipt() { return receipt; }
    public void syncAsync() { synced = true; }
    public boolean isSynced() { return synced; }
}
